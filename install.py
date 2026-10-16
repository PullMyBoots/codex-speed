#!/usr/bin/env python3
"""Source-only installer. No Codex version whitelist or startup version probes."""
import argparse
import contextlib
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
PATCH=ROOT/'patches/codex.patch'
MARKER='# codex-speed managed launcher'
FEATURES=(b'CXSTATUSLINE_COMMAND',b'model/streamMetrics',b'stream_kind',b'sample_interval_ms')


def exists(p): return os.path.lexists(p)

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def atomic(p,text,mode=0o600):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=p.name+'.tmp-',dir=p.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(text)
        os.chmod(tmp,mode);os.replace(tmp,p)
    finally:
        if exists(tmp):os.unlink(tmp)


def run(args,cwd=None,env=None,capture=False):
    print('+ '+shlex.join([str(x) for x in args]),flush=True)
    return subprocess.run([str(x) for x in args],cwd=cwd,env=env,check=True,
                          text=True,stdout=subprocess.PIPE if capture else None)


def download(url,dest,env):
    dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
    proxies={k:env[k.upper()+'_PROXY'] for k in ('http','https') if env.get(k.upper()+'_PROXY')}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    tmp=dest.with_suffix(dest.suffix+'.download')
    for attempt in range(3):
        try:
            print('Download: '+url,flush=True)
            with opener.open(url,timeout=120) as src,tmp.open('wb') as out:shutil.copyfileobj(src,out)
            os.replace(tmp,dest);return dest
        except Exception:
            tmp.unlink(missing_ok=True)
            if attempt==2:raise
            time.sleep(1+attempt)


def package_candidates(codex_bin=None):
    candidates=[]
    executable=codex_bin or shutil.which('codex')
    if executable:
        for parent in list(Path(executable).resolve().parents)[:5]:
            candidates.append(parent)
            candidates.extend(parent.glob('vendor/*'))
    candidates.extend([Path.home()/'.local/share/codex/current',Path.home()/'.local/libexec/cxstatusline/current'])
    npm=shutil.which('npm')
    if npm:
        r=subprocess.run([npm,'root','-g'],capture_output=True,text=True)
        if r.returncode==0:
            modules=Path(r.stdout.strip())
            candidates.extend(modules.glob('@openai/codex/node_modules/@openai/codex-*/vendor/*'))
            candidates.extend(modules.glob('@openai/codex-*/vendor/*'))
    seen=set()
    for p in candidates:
        p=p.resolve()
        if p not in seen and (p/'codex-package.json').is_file():yield p
        seen.add(p)


def has_metrics(binary):
    try:
        with Path(binary).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            return all(data.find(feature)>=0 for feature in FEATURES)
    except (OSError,ValueError):return False


def binary_at(package,name):
    return next((p for p in (package/'bin'/name,package/name) if p.is_file()),package/'bin'/name)


def patch_candidates(source):
    # Release metadata only orders candidates. A missing name never rejects a
    # source tree: every available patch still gets an actual applicability check.
    candidates=[]
    manifest=Path(source)/'codex-rs/Cargo.toml'
    if manifest.is_file():
        version=re.search(r'\[workspace.package\]\s*version\s*=\s*"([^"]+)"',manifest.read_text())
        if version and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*',version.group(1)):
            candidates.append(ROOT/'patches'/('codex-'+version.group(1)+'.patch'))
    candidates.extend([PATCH,*sorted((ROOT/'patches').glob('codex-*.patch'))])
    return list(dict.fromkeys(p for p in candidates if p.is_file()))


def check_patch(source,apply=False):
    base=['git','-C',str(source),'apply']
    candidates=patch_candidates(source)
    # Inspect every reverse check first so a retry never layers another variant
    # onto a source tree that already contains one of our complete patches.
    for patch in candidates:
        reverse=subprocess.run(base+['--reverse','--check',str(patch)],capture_output=True,text=True)
        if reverse.returncode==0:return 'already applied'
    failures=[]
    for patch in candidates:
        probe=subprocess.run(base+['--check',str(patch)],capture_output=True,text=True)
        if probe.returncode==0:
            if apply:
                print('Selected source patch: '+patch.name,flush=True)
                run(base+[str(patch)])
            return 'applicable'
        failures.append(patch.name+':\n'+probe.stderr)
    raise RuntimeError('No source patch applies. No version whitelist was consulted; these are actual source conflicts.\n'+'\n'.join(failures)+'\nAsk Codex to adapt a patch to this source. No launcher was changed.')


def build_package(args,cache,env,installed):
    if installed is None:
        raise RuntimeError('Cannot locate the installed Codex runtime package. Pass --codex-package PATH. --upstream-version selects source only; runtime assets are still required. Existing Codex was not probed with --version.')
    for name in ('codex-path','codex-resources'):
        if not (installed/name).is_dir():raise RuntimeError('Missing runtime assets: '+str(installed/name))
    metadata=json.loads((installed/'codex-package.json').read_text())
    version=args.upstream_version or metadata.get('version')
    if not version or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*',version):raise RuntimeError('Invalid source tag')
    tag=version if version.startswith('rust-v') else 'rust-v'+version
    source=cache/'sources'/tag
    source.parent.mkdir(parents=True,exist_ok=True)
    if not (source/'.git').exists():
        if source.exists():raise RuntimeError('Incomplete checkout; preserve/remove it and retry: '+str(source))
        run(['git','clone','--depth','1','--branch',tag,'--single-branch','https://github.com/openai/codex.git',source],env=env)
    check_patch(source,apply=True)
    rust=source/'codex-rs'
    toolchain=re.search(r'channel\s*=\s*"([^"]+)"',(rust/'rust-toolchain.toml').read_text()).group(1)
    cargo_bin=Path.home()/'.cargo/bin'
    env['PATH']=str(cargo_bin)+os.pathsep+env['PATH']
    if not shutil.which('rustup',path=env['PATH']):
        bootstrap=download('https://sh.rustup.rs',cache/'rustup-init.sh',env)
        run(['sh',bootstrap,'-y','--profile','minimal','--no-modify-path','--default-toolchain','none'],env=env)
    run(['rustup','toolchain','install',toolchain,'--profile','minimal'],env=env)
    host=run(['rustc','+'+toolchain,'-vV'],env=env,capture=True).stdout
    target=re.search(r'^host: (.+)$',host,re.M).group(1)
    env['CARGO_TARGET_DIR']=str(cache/'target')
    # Follow upstream Codex's own setup-rusty-v8 action, including its two-level
    # checksum verification. Cargo's default denoland URL lacks these artifacts.
    lock=(rust/'Cargo.lock').read_text()
    v8=re.search(r'\[\[package\]\]\s*name = "v8"\s*version = "([^"]+)"',lock)
    if v8:
        v8=v8.group(1);profile='ptrcomp_sandbox_release'
        names=[f'librusty_v8_{profile}_{target}.a.gz',f'src_binding_{profile}_{target}.rs']
        checksum=f'rusty_v8_{profile}_{target}.sha256'
        trusted=source/'third_party/v8'/('rusty_v8_'+v8.replace('.','_')+'_release_manifests.sha256')
        if trusted.exists():
            asset_base=f'https://github.com/openai/codex/releases/download/rusty-v8-v{v8}'
            asset_dir=cache/'v8'/v8/target
            checks=download(asset_base+'/'+checksum,asset_dir/checksum,env)
            expected=dict((line.split()[1].lstrip('*'),line.split()[0]) for line in trusted.read_text().splitlines() if line.strip())
            if digest(checks)!=expected.get(checksum):raise RuntimeError('V8 checksum manifest mismatch')
            file_hashes=dict((line.split()[1].lstrip('*'),line.split()[0]) for line in checks.read_text().splitlines() if line.strip())
            if set(file_hashes)!=set(names):raise RuntimeError('Unexpected V8 artifact manifest')
            for name in names:
                file=asset_dir/name
                if not file.exists() or digest(file)!=file_hashes[name]:download(asset_base+'/'+name,file,env)
                if digest(file)!=file_hashes[name]:raise RuntimeError('V8 checksum mismatch: '+name)
            env['RUSTY_V8_ARCHIVE']=str(asset_dir/names[0])
            env['RUSTY_V8_SRC_BINDING_PATH']=str(asset_dir/names[1])
    run(['cargo','+'+toolchain,'build','--release','--locked','-j',str(args.jobs),'-p','codex-code-mode-host','--bin','codex-code-mode-host'],cwd=rust,env=env)
    run(['cargo','+'+toolchain,'rustc','--release','--locked','-j',str(args.jobs),'-p','codex-cli','--bin','codex','--','-C','lto=off','-C','codegen-units=32'],cwd=rust,env=env)
    # Build a package layout locally. Runtime assets come from the selected
    # installed CLI; its account/model configuration is never copied.
    package=cache/'built-package';package.mkdir(exist_ok=True)
    (package/'bin').mkdir(exist_ok=True)
    for name in ('codex','codex-code-mode-host'):
        shutil.copy2(cache/'target/release'/name,package/'bin'/name)
        strip=shutil.which('strip')
        if strip:run([strip,'-S',package/'bin'/name])
    for name in ('codex-path','codex-resources'):
        if not (installed/name).is_dir():raise RuntimeError('Missing runtime assets: '+str(installed/name))
        shutil.copytree(installed/name,package/name,dirs_exist_ok=True)
    metadata.update(version=version.removeprefix('rust-v'),target=target)
    atomic(package/'codex-package.json',json.dumps(metadata,indent=2)+'\n')
    return package


def scripts(prefix,python):
    prefix=Path(prefix);q=shlex.quote
    renderer=f'{q(str(python))} {q(str(prefix/"current/render.py"))}'
    run_script='#!/bin/sh\n'+MARKER+'\n'
    run_script+='if [ -z "${CXSTATUSLINE_COMMAND:-}" ]; then\n  export CXSTATUSLINE_COMMAND='+q(renderer)+'\nfi\n'
    run_script+='private_backend=--no-daemon\nfor arg do\n  case "$arg" in --remote|--remote=*|--no-daemon) private_backend= ;; esac\ndone\n'
    run_script+='if [ -n "$private_backend" ]; then\n  exec '+q(str(prefix/'current/bin/codex'))+' "$private_backend" "$@"\nfi\n'
    run_script+='exec '+q(str(prefix/'current/bin/codex'))+' "$@"\n'
    uninstall='#!/bin/sh\n'+MARKER+'\nexec '+q(str(python))+' '+q(str(prefix/'current/install.py'))+' uninstall --prefix '+q(str(prefix))+' "$@"\n'
    return {'codex':run_script,'codex-speed':run_script,'codex-speed-uninstall':uninstall}


def install_package(package,prefix,bin_dir,alias=True):
    package=Path(package).resolve();prefix=Path(prefix).resolve();bin_dir=Path(bin_dir).resolve()
    if any('\n' in str(p) for p in (prefix,bin_dir)):raise RuntimeError('Paths cannot contain newlines')
    binary=binary_at(package,'codex')
    if not has_metrics(binary):raise RuntimeError('This CLI lacks native streaming metrics. Use the default source install; configuring stock Codex alone cannot add them.')
    for name in ('codex','codex-code-mode-host'):
        file=binary_at(package,name)
        run([file,'--help'],capture=True)
    state_file=prefix/'installation.json'
    state=json.loads(state_file.read_text()) if state_file.exists() else {'format':1,'prefix':str(prefix),'bin_dir':str(bin_dir),'entries':{},'releases':[]}
    if state.get('format')!=1 or state.get('prefix')!=str(prefix) or state.get('bin_dir')!=str(bin_dir):raise RuntimeError('Existing installation uses a different prefix/bin directory')
    launchers=scripts(prefix,Path(sys.executable).resolve())
    if not alias:launchers.pop('codex')
    for name in launchers:
        dest=bin_dir/name;old=state['entries'].get(name)
        if exists(dest) and dest.is_dir() and not dest.is_symlink():raise RuntimeError('Launcher is a directory: '+str(dest))
        if old and exists(dest) and (dest.is_symlink() or digest(dest)!=old['hash']):raise RuntimeError('Launcher was modified; preserve it before reinstalling: '+str(dest))
    prefix.mkdir(parents=True,exist_ok=True);bin_dir.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256((digest(binary)+digest(binary_at(package,'codex-code-mode-host'))+digest(package/'codex-package.json')+digest(ROOT/'render.py')+digest(Path(__file__))).encode()).hexdigest()[:16]
    release=prefix/'releases'/identity;release.parent.mkdir(exist_ok=True)
    if not release.exists():
        with tempfile.TemporaryDirectory(prefix='.stage-',dir=release.parent) as folder:
            stage=Path(folder)/'package';stage.mkdir();(stage/'bin').mkdir()
            for name in ('codex','codex-code-mode-host'):shutil.copy2(binary_at(package,name),stage/'bin'/name)
            for name in ('codex-path','codex-resources'):
                if not (package/name).is_dir():raise RuntimeError('Missing runtime assets: '+str(package/name))
                shutil.copytree(package/name,stage/name)
            shutil.copy2(package/'codex-package.json',stage/'codex-package.json')
            shutil.copy2(ROOT/'render.py',stage/'render.py');shutil.copy2(Path(__file__),stage/'install.py')
            shutil.copy2(ROOT/'LICENSE',stage/'LICENSE')
            if (ROOT/'NOTICE').exists():shutil.copy2(ROOT/'NOTICE',stage/'NOTICE')
            shutil.copy2(ROOT/'patches/CXSTATUSLINE-LICENSE',stage/'CXSTATUSLINE-LICENSE')
            os.rename(stage,release)
    for name,text in launchers.items():
        dest=bin_dir/name
        if name not in state['entries']:
            backup=None
            if exists(dest):
                backup=dest.with_name('.'+name+'.before-codex-speed-'+str(time.time_ns()))
                os.rename(dest,backup)
            state['entries'][name]={'backup':str(backup) if backup else None}
        state['entries'][name]['hash']=hashlib.sha256(text.encode()).hexdigest()
    if str(release) not in state['releases']:state['releases'].append(str(release))
    state['active']=str(release)
    atomic(state_file,json.dumps(state,indent=2)+'\n')
    next_link=prefix/('current.next-'+str(os.getpid()))
    next_link.unlink(missing_ok=True);next_link.symlink_to(release.relative_to(prefix));os.replace(next_link,prefix/'current')
    for name,text in launchers.items():atomic(bin_dir/name,text,0o755)
    print('\nInstalled. Restart Codex, then run: '+shlex.quote(str(bin_dir/'codex-speed')))
    print('Uninstall/restore launchers: '+shlex.quote(str(bin_dir/'codex-speed-uninstall')))
    print('Your ~/.codex, model routing, credentials and native status-line selections were preserved.')
    print('If another codex precedes this directory in PATH, use codex-speed or the full path above.')
    return state


def uninstall(prefix):
    prefix=Path(prefix).resolve();state_file=prefix/'installation.json';state=json.loads(state_file.read_text())
    if state.get('format')!=1 or state.get('prefix')!=str(prefix):raise RuntimeError('Invalid installation state')
    bin_dir=Path(state['bin_dir'])
    for name,info in state['entries'].items():
        if Path(name).name!=name:raise RuntimeError('Invalid launcher name')
        dest=bin_dir/name;backup=Path(info['backup']) if info.get('backup') else None
        if exists(dest) and (dest.is_symlink() or not dest.is_file() or digest(dest)!=info['hash']):raise RuntimeError('Launcher was modified; nothing removed: '+str(dest))
        if backup and (not exists(backup) or backup.parent!=bin_dir):raise RuntimeError('Backup missing; nothing removed: '+str(backup))
    for release in state['releases']:
        if Path(release).parent!=prefix/'releases':raise RuntimeError('Invalid release path')
    for name,info in state['entries'].items():
        dest=bin_dir/name
        if exists(dest):dest.unlink()
        if info.get('backup'):os.rename(info['backup'],dest)
    for release in state['releases']:shutil.rmtree(release)
    (prefix/'current').unlink(missing_ok=True);state_file.unlink()
    with contextlib.suppress(OSError):(prefix/'releases').rmdir()
    print('Uninstalled; previous launchers restored. Your Codex configuration was preserved.')


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',nargs='?',choices=('install','doctor','uninstall'),default='install')
    p.add_argument('--prefix',type=Path,default=Path.home()/'.local/share/codex-speed')
    p.add_argument('--bin-dir',type=Path,default=Path.home()/'.local/bin')
    p.add_argument('--cache-dir',type=Path,default=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'codex-speed')
    p.add_argument('--from-build',type=Path,help='Reuse a package layout with already-patched binaries, no compilation')
    p.add_argument('--codex-package',type=Path,help='Installed native package containing codex-package.json and runtime assets')
    p.add_argument('--codex-bin',help='Hint for locating the existing installation')
    p.add_argument('--upstream-version',help='Source tag selection only; any tag is attempted, no version whitelist')
    p.add_argument('--check-source',type=Path,help='Read-only patch check, then exit')
    p.add_argument('--jobs',type=int,default=min(4,os.cpu_count() or 2))
    p.add_argument('--no-codex-link',action='store_true',help='Only install codex-speed, leave the codex entry alone')
    p.add_argument('--proxy',help='Proxy only for install/build downloads; no persistent proxy configuration')
    return p


def main():
    if sys.version_info<(3,9):raise RuntimeError('Python 3.9+ is required')
    args=parser().parse_args()
    if args.action=='uninstall':uninstall(args.prefix);return
    if args.check_source:print(check_patch(args.check_source));return
    if args.jobs<1:raise RuntimeError('--jobs must be positive')
    if platform.system() not in ('Linux','Darwin'):raise RuntimeError('Use Linux/macOS or Windows WSL2. Native Windows is not supported by this installer.')
    installed=args.codex_package.resolve() if args.codex_package else next(package_candidates(args.codex_bin),None)
    own=args.prefix.resolve()/'current'
    if not args.codex_package and not args.upstream_version and (own/'codex-package.json').is_file():installed=own.resolve()
    tools={name:bool(shutil.which(name)) for name in ('git','cc','c++','make','pkg-config')}
    if args.action=='doctor':
        print(json.dumps({'python':sys.version.split()[0],'tools':tools,'codex_package':str(installed) if installed else None,'native_stream_metrics':has_metrics(binary_at(installed,'codex')) if installed else False,'source_patch_base':'0.163.0','codex_version_gates':False,'startup_version_probes':False},indent=2));return
    if args.from_build:install_package(args.from_build,args.prefix,args.bin_dir,not args.no_codex_link);return
    if installed and not args.upstream_version and has_metrics(binary_at(installed,'codex')):
        print('Reusing the installed CLI: native streaming-metrics support is already present.',flush=True)
        install_package(installed,args.prefix,args.bin_dir,not args.no_codex_link);return
    missing=[name for name,ok in tools.items() if not ok]
    if missing:raise RuntimeError('Missing build tools: '+', '.join(missing)+'. See AGENTS.md / docs/INSTALL.md. Nothing was installed.')
    env=os.environ.copy()
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(key,None)
    if args.proxy:env.update(HTTP_PROXY=args.proxy,HTTPS_PROXY=args.proxy)
    cache=args.cache_dir.resolve();cache.mkdir(parents=True,exist_ok=True)
    print('First install builds a patched CLI. Allow tens of minutes, dependency downloads and at least 20 GiB disk space.\nNo Codex version whitelist; existing Codex executables/configuration will not be overwritten.',flush=True)
    built=build_package(args,cache,env,installed)
    install_package(built,args.prefix,args.bin_dir,not args.no_codex_link)


if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:
        print('Install error: '+str(error),file=sys.stderr);sys.exit(1)

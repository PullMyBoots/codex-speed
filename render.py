#!/usr/bin/env python3
"""Render native decode metrics using Python's standard library only."""
import json
import math
import os
import sys


def render(data):
    m=data.get('stream_metrics') or {}
    rate=m.get('output_tps')
    valid=isinstance(rate,(int,float)) and not isinstance(rate,bool) and math.isfinite(rate) and rate>=0
    base='Summary' if m.get('stream_kind')=='summary' else 'Decode'
    phase=m.get('phase')
    suffix=' (stopped)' if phase=='interrupted' else ' (last)' if phase=='complete' or (phase=='waiting' and valid) else ' (tool)' if m.get('stream_kind')=='tool' else ' (think)' if m.get('stream_kind')=='reasoning' else ''
    result=f'{base}{suffix}: '+(f'~{rate:.1f} t/s' if valid else '—')
    usage=data.get('usage') or {}
    total=usage.get('output_tokens')
    if isinstance(total,(int,float)) and not isinstance(total,bool) and total>=0:
        result+=f' | Out: {int(total):,}'
    try:width=int(os.environ.get('CXSTATUSLINE_WIDTH','120'))
    except ValueError:width=120
    # All default labels are single terminal cells; trim before returning one row.
    return result[:max(0,width)]


if __name__=='__main__':
    try:print(render(json.load(sys.stdin)))
    except (ValueError,TypeError,AttributeError):print('Decode: —')

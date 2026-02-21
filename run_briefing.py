#!/usr/bin/env python3
"""Run the morning briefing directly."""

import sys
sys.path.insert(0, '/home/openclaw/.openclaw/workspace/projects/morning-briefing/src')

from morning_briefing.cli import main

if __name__ == '__main__':
    sys.argv = ['mbrief', 'generate', '--send']
    main()

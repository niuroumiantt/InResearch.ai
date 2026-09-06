#!/usr/bin/env python3
"""Report the permanent Spark reader state; never launch the retired batch agent."""
import json
import research


def main():
    reader = research.build_snapshot()['reader']
    print(json.dumps(reader, ensure_ascii=False, indent=2))
    print('常驻服务：spark / inresearch-reader.service；操作见 docs/local_reader/SPARK_OPERATIONS.md。')
    return 0 if reader.get('status') not in ('not_connected', 'degraded') else 1


if __name__ == '__main__':
    raise SystemExit(main())

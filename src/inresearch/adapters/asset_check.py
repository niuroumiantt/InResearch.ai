"""Check the same visual-input contract used by import and HTTP."""
import sys
from inresearch.materials import model_assets


def main():
    try:
        manifest = model_assets.read_manifest(verify_files=True)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"模型登记不通过：{exc}")
        return 1
    registered = {m['file'] for m in manifest['models']}
    for entry in manifest['models']:
        print(f"{entry['file']} → {entry['page']} · {entry['status']} · {entry['sha256'][:12]}")
    unregistered = sorted(p.name for p in model_assets.model_directory().glob('*.glb') if p.name not in registered)
    for name in unregistered:
        print(f"未登记文件保留且不发布：{name}；若导入曾中断，请用原输入重试")
    print(f"通过：{len(registered)} 条登记；{len(unregistered)} 个未登记文件；仅 adopted 进入场景。")
    return 0


if __name__ == '__main__':
    sys.exit(main())

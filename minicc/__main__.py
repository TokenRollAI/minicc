"""
MiniCC CLI 入口

支持以下启动方式:
    $ python -m minicc
    $ minicc (通过 pyproject.toml scripts 配置)
"""

from .app import main

if __name__ == "__main__":
    main()

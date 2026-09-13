"""Authentication views use one layout and shared form interaction."""
from html import escape
from inresearch.paths import project_root


def auth_page(name, title):
    folder = project_root() / 'web/pages/auth'
    return (folder / 'layout.html').read_text().replace('@@TITLE@@', escape(title)).replace('@@BODY@@', (folder / (name + '.html')).read_text())


LOGIN_PAGE = auth_page('login', '登录')
PASSWD_PAGE = auth_page('password', '修改密码')
FORBIDDEN_PAGE = auth_page('forbidden', '无权访问')

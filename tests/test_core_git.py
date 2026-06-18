from gitscanner.core.git import build_clone_url, build_github_headers, build_gitlab_headers, get_repo_info


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def test_build_headers_with_explicit_tokens(monkeypatch):
    monkeypatch.delenv('GITSCANNER_TOKEN', raising=False)
    assert build_github_headers('abc')['Authorization'] == 'token abc'
    assert build_gitlab_headers('xyz')['PRIVATE-TOKEN'] == 'xyz'


def test_build_clone_url_for_gitlab_public_and_custom_api_url():
    assert build_clone_url('gitlab-org/repo', 'https://gitlab.com/api/v4', provider='gitlab').endswith('.git')
    assert build_clone_url('group/repo', 'https://gitlab.example.com/api/v4', provider='gitlab').startswith('https://gitlab.example.com/')


def test_get_repo_info_returns_none_on_non_200():
    def fake_get(url, headers=None):
        return DummyResponse(status_code=404)

    assert get_repo_info('org/repo', 'https://api.github.com', get=fake_get) is None


def test_get_repo_info_returns_payload_on_200():
    def fake_get(url, headers=None):
        return DummyResponse(status_code=200, payload={'name': 'repo'})

    assert get_repo_info('org/repo', 'https://api.github.com', get=fake_get)['name'] == 'repo'

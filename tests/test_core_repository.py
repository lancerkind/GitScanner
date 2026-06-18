from gitscanner.core.repository import RepositoryClient


def test_repository_client_checkout_maps_result_to_dataclass():
    def fake_clone_and_count(repo_name, api_base_url='https://api.github.com', provider='github', token=None):
        assert repo_name == 'org/repo'
        return {'path': '/tmp/repo', 'clone_url': 'https://example.com/org/repo.git'}

    client = RepositoryClient(clone_and_count_func=fake_clone_and_count)
    checkout = client.checkout('org/repo')

    assert str(checkout.path) == '/tmp/repo'
    assert checkout.clone_url == 'https://example.com/org/repo.git'

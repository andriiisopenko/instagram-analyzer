from instagram_analyzer.analyzer import find_non_followers


def test_find_non_followers() -> None:
    following = {"alice", "bob", "charlie"}
    followers = {"alice", "charlie", "david"}

    assert find_non_followers(following, followers) == {"bob"}


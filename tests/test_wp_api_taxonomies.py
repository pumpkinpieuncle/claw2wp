"""Taxonomy resolution regressions; every HTTP request is mocked."""
from unittest.mock import Mock

import pytest

from claw2wp.wp_api import WPApi


@pytest.fixture(params=[
    ('resolve_wp_category_ids', '/wp/v2/categories'),
    ('resolve_wp_tag_ids', '/wp/v2/tags'),
    ('resolve_wc_category_ids', '/wc/v3/products/categories'),
])
def resolver(request):
    api = WPApi({'url': 'https://example.invalid'})
    api._request = Mock(return_value=Mock(status_code=200, json=Mock(return_value=[
        {'id': 82, 'name': '开发', 'slug': 'development'},
        {'id': 7, 'name': 'News', 'slug': 'news'},
        {'id': 99, 'name': '82', 'slug': 'numeric-name'},
    ])))
    return getattr(api, request.param[0]), api._request, request.param[1]


def test_integer_ids_need_no_lookup(resolver):
    resolve, http, _ = resolver
    assert resolve([82, 7, 82]) == [82, 7]
    http.assert_not_called()


def test_mixed_ids_names_and_slugs_are_deduplicated_in_order(resolver):
    resolve, http, path = resolver
    assert resolve([' News ', 82, 'DEVELOPMENT', 7, '开发', 'unknown']) == [7, 82]
    http.assert_called_once_with('GET', path, params={'per_page': 100})


def test_comma_separated_names_keep_numeric_strings_as_names(resolver):
    resolve, http, _ = resolver
    assert resolve(' News, , DEVELOPMENT, 82, unknown ') == [7, 82, 99]
    assert resolve(['82']) == [99]
    assert resolve(['news', 'NEWS']) == [7]
    http.assert_called_once()


@pytest.mark.parametrize('value', [None, [], '', ' , ', [True, False, None, '', '  ']])
def test_empty_and_boolean_values_are_not_ids(resolver, value):
    resolve, http, _ = resolver
    assert resolve(value) == []
    http.assert_not_called()


def test_boolean_does_not_collide_with_integer_id(resolver):
    resolve, http, _ = resolver
    assert resolve([True, 1, False, 82]) == [1, 82]
    http.assert_not_called()

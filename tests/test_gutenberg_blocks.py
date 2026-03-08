# -*- coding: utf-8 -*-
"""验证 Gutenberg 块转换：二级标题、表格、图片等与 WP 古腾堡一致。"""
from bs4 import BeautifulSoup
from claw2wp.gutenberg import soup_to_gutenberg


def test_paragraph_with_single_image_becomes_image_block():
    """段落内仅一张图 -> wp:image 块。"""
    html = '<p><img alt="" src="pic.jpg" /></p>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert 'wp:image' in out
    assert 'wp-block-image' in out
    assert '<!-- wp:paragraph -->' not in out or out.find('wp:image') < out.find('wp:paragraph')


def test_paragraph_with_only_multiple_images_becomes_multiple_image_blocks():
    """段落内仅多张图 -> 每张一个 wp:image 块。"""
    html = '<p><img src="a.jpg" /><img src="b.jpg" /></p>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert out.count('<!-- wp:image') == 2
    assert '<!-- wp:paragraph -->' not in out


def test_separator_has_wp_class():
    """hr 带 wp-block-separator has-alpha-channel-opacity。"""
    html = '<hr />'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert 'wp:separator' in out
    assert 'wp-block-separator' in out
    assert 'has-alpha-channel-opacity' in out


def test_table_has_figure_wp_block_table():
    html = '<table><tr><th>A</th></tr><tr><td>1</td></tr></table>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert 'wp-block-table' in out
    assert '<figure' in out


def test_list_has_wp_block_list():
    html = '<ul><li>a</li></ul>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert 'wp-block-list' in out


def test_heading_h2_has_level():
    html = '<h2>二级标题</h2>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert 'wp:heading' in out
    assert 'level' in out and '2' in out  # wp:heading {"level": 2}
    assert 'wp-block-heading' in out


def test_mixed_blocks():
    html = '<h2>Title</h2><p>Text</p><p><img src="x.jpg" /></p><table><tr><td>1</td></tr></table>'
    out = soup_to_gutenberg(BeautifulSoup(html, 'html.parser'))
    assert out.count('<!-- wp:heading') == 1
    assert out.count('<!-- wp:paragraph') == 1
    assert out.count('<!-- wp:image') == 1
    assert out.count('<!-- wp:table') == 1


if __name__ == '__main__':
    test_paragraph_with_single_image_becomes_image_block()
    test_paragraph_with_only_multiple_images_becomes_multiple_image_blocks()
    test_separator_has_wp_class()
    test_table_has_figure_wp_block_table()
    test_list_has_wp_block_list()
    test_heading_h2_has_level()
    test_mixed_blocks()
    print('All Gutenberg block tests passed.')

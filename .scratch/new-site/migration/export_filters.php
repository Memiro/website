<?php
/** Выгрузка справочников фильтров старого сайта. Только чтение. */
$out = [];
$ids = get_posts([
    'post_type'      => 'filter-field',
    'post_status'    => 'any',
    'posts_per_page' => -1,
    'fields'         => 'ids',
]);
foreach ($ids as $id) {
    $post = get_post($id);
    $out[] = [
        'ID'     => $id,
        'slug'   => $post->post_name,
        'title'  => $post->post_title,
        'parent' => $post->post_parent,
        'meta'   => array_map(function ($values) {
            return array_map('maybe_unserialize', $values);
        }, get_post_meta($id)),
    ];
}
echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);

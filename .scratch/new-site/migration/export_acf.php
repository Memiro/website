<?php
/** Выгрузка определений ACF-полей (label + choices). Только чтение. */
$out = [];
$ids = get_posts([
    'post_type'      => 'acf-field',
    'post_status'    => 'any',
    'posts_per_page' => -1,
    'fields'         => 'ids',
]);
foreach ($ids as $id) {
    $post = get_post($id);
    $out[] = [
        'key'     => $post->post_name,
        'name'    => $post->post_excerpt,
        'label'   => $post->post_title,
        'config'  => maybe_unserialize($post->post_content),
    ];
}
echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);

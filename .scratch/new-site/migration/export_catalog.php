<?php
/**
 * Выгрузка каталога старого сайта в JSON. Только чтение.
 * Запуск на сервере: wp eval-file export_catalog.php > catalog.json
 */

function memiro_attachment($id) {
    if (!$id || !is_numeric($id)) {
        return null;
    }
    $url = wp_get_attachment_url((int) $id);
    if (!$url) {
        return null;
    }
    $meta = wp_get_attachment_metadata((int) $id);
    return [
        'id'     => (int) $id,
        'url'    => $url,
        'file'   => get_post_meta((int) $id, '_wp_attached_file', true),
        'alt'    => get_post_meta((int) $id, '_wp_attachment_image_alt', true),
        'width'  => isset($meta['width']) ? $meta['width'] : null,
        'height' => isset($meta['height']) ? $meta['height'] : null,
    ];
}

$out = ['post_types' => [], 'items' => [], 'pages' => [], 'posts' => [], 'faq' => []];

foreach (['catalog', 'page', 'post', 'faq'] as $type) {
    $ids = get_posts([
        'post_type'      => $type,
        'post_status'    => 'any',
        'posts_per_page' => -1,
        'fields'         => 'ids',
        'orderby'        => 'ID',
        'order'          => 'ASC',
    ]);
    $bucket = $type === 'catalog' ? 'items' : ($type === 'page' ? 'pages' : ($type === 'post' ? 'posts' : 'faq'));
    foreach ($ids as $id) {
        $post = get_post($id);
        $row = [
            'ID'          => $id,
            'slug'        => $post->post_name,
            'title'       => $post->post_title,
            'status'      => $post->post_status,
            'date'        => $post->post_date,
            'modified'    => $post->post_modified,
            'url'         => get_permalink($id),
            'content'     => $post->post_content,
            'excerpt'     => $post->post_excerpt,
            'menu_order'  => $post->menu_order,
            'thumbnail'   => memiro_attachment(get_post_thumbnail_id($id)),
            'meta'        => [],
            'terms'       => [],
        ];
        foreach (get_post_meta($id) as $key => $values) {
            $row['meta'][$key] = array_map(function ($v) {
                $un = maybe_unserialize($v);
                return $un;
            }, $values);
        }
        foreach (get_object_taxonomies($type) as $tax) {
            $terms = wp_get_object_terms($id, $tax, ['fields' => 'all']);
            if (!is_wp_error($terms) && $terms) {
                foreach ($terms as $t) {
                    $row['terms'][] = ['taxonomy' => $tax, 'slug' => $t->slug, 'name' => $t->name];
                }
            }
        }
        $out[$bucket][] = $row;
    }
}

echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_PARTIAL_OUTPUT_ON_ERROR);

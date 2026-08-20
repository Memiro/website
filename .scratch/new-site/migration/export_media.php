<?php
/** Выгрузка вложений, на которые ссылается каталог. Только чтение. */
$ids = get_posts([
    'post_type'      => 'catalog',
    'post_status'    => 'any',
    'posts_per_page' => -1,
    'fields'         => 'ids',
]);

$wanted = [];
foreach ($ids as $id) {
    $img = get_post_meta($id, 'img', true);
    if ($img) {
        $wanted[(int) $img] = true;
    }
    $gallery = get_post_meta($id, 'gallery', true);
    if (is_array($gallery)) {
        foreach ($gallery as $g) {
            $wanted[(int) $g] = true;
        }
    }
}

$upload = wp_get_upload_dir();
$out = [];
foreach (array_keys($wanted) as $id) {
    $meta = wp_get_attachment_metadata($id);
    $file = get_post_meta($id, '_wp_attached_file', true);
    $sizes = [];
    if (isset($meta['sizes']) && is_array($meta['sizes'])) {
        $dir = trim(dirname($file), '.');
        foreach ($meta['sizes'] as $name => $size) {
            $sizes[$name] = [
                'file'   => ($dir ? $dir . '/' : '') . $size['file'],
                'width'  => $size['width'],
                'height' => $size['height'],
            ];
        }
    }
    $out[$id] = [
        'id'       => $id,
        'file'     => $file,
        'mime'     => get_post_mime_type($id),
        'alt'      => get_post_meta($id, '_wp_attachment_image_alt', true),
        'width'    => isset($meta['width']) ? $meta['width'] : null,
        'height'   => isset($meta['height']) ? $meta['height'] : null,
        'sizes'    => $sizes,
    ];
}

echo json_encode(['basedir' => $upload['basedir'], 'baseurl' => $upload['baseurl'], 'attachments' => $out], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);

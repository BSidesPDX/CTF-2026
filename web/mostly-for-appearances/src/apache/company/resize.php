<?php
// Dynamic image resizing script

// Get parameters
$imagePath = $_GET['image'] ?? '';
$width = isset($_GET['w']) ? (int)$_GET['w'] : 0;
$height = isset($_GET['h']) ? (int)$_GET['h'] : 0;

// Validate image path
if (empty($imagePath) || !file_exists($imagePath)) {
    http_response_code(404);
    exit('Image not found');
}

// Validate dimensions
if ($width <= 0 && $height <= 0) {
    http_response_code(400);
    exit('Invalid dimensions');
}

// Limit maximum size to prevent abuse
$maxSize = 2000;
if ($width > $maxSize) {
  $width = $maxSize;
}
if ($height > $maxSize) {
  $height = $maxSize;
}

// Validate MIME type using finfo
$finfo = new finfo(FILEINFO_MIME_TYPE);
$mimeType = $finfo->file($imagePath);
$supportedMimeTypes = ["image/jpeg", "image/png", "image/gif"];
if (!in_array($mimeType, $supportedMimeTypes, true)) {
  http_response_code(400);
  exit("Invalid image");
}

// Get image info
$imageInfo = getimagesize($imagePath);
if (!$imageInfo) {
    http_response_code(400);
    exit('Invalid image');
}

list($origWidth, $origHeight, $imageType) = $imageInfo;

// Calculate dimensions maintaining aspect ratio
if ($width > 0 && $height > 0) {
    // Both dimensions specified - use them
    $newWidth = $width;
    $newHeight = $height;
} elseif ($width > 0) {
    // Only width specified
    $newWidth = $width;
    $newHeight = (int)($origHeight * ($width / $origWidth));
} else {
    // Only height specified
    $newHeight = $height;
    $newWidth = (int)($origWidth * ($height / $origHeight));
}

// Create source image
switch ($imageType) {
    case IMAGETYPE_JPEG:
        $srcImage = imagecreatefromjpeg($imagePath);
        break;
    case IMAGETYPE_PNG:
        $srcImage = imagecreatefrompng($imagePath);
        break;
    case IMAGETYPE_GIF:
        $srcImage = imagecreatefromgif($imagePath);
        break;
    default:
        http_response_code(400);
        exit('Unsupported image type');
}

// Create new image
$dstImage = imagecreatetruecolor($newWidth, $newHeight);

// Preserve transparency for PNG and GIF
if ($imageType == IMAGETYPE_PNG || $imageType == IMAGETYPE_GIF) {
    imagealphablending($dstImage, false);
    imagesavealpha($dstImage, true);
    $transparent = imagecolorallocatealpha($dstImage, 255, 255, 255, 127);
    imagefilledrectangle($dstImage, 0, 0, $newWidth, $newHeight, $transparent);
}

// Resize image
imagecopyresampled($dstImage, $srcImage, 0, 0, 0, 0, $newWidth, $newHeight, $origWidth, $origHeight);

// Output image
header('Content-Type: ' . image_type_to_mime_type($imageType));
header('Cache-Control: public, max-age=31536000'); // Cache for 1 year

switch ($imageType) {
    case IMAGETYPE_JPEG:
        imagejpeg($dstImage, null, 85);
        break;
    case IMAGETYPE_PNG:
        imagepng($dstImage);
        break;
    case IMAGETYPE_GIF:
        imagegif($dstImage);
        break;
}

// Clean up
imagedestroy($srcImage);
imagedestroy($dstImage);

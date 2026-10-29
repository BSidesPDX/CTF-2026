<?php

// use admin.php to manage these
$available_versions = [
    'Y2xlYW51cA==' => 'cleanup',
    'djA=' => '0',
    'djE=' => '1',
    'djI=' => '2',
];

$params = $_GET;

var_dump($params);

$version = $_GET['version'];

if (array_key_exists($version, $available_versions)) {
    echo file_get_contents($_SERVER['DOCUMENT_ROOT'] . '/../bins/' . $available_versions[$version]);
}
else {
    echo "not found";
}

<?php

$admin_passhash = '$2y$12$F7IJ3pkEcqpU8QfNz5YZ4Oz3HlkPFhKCaOgkEnzvMvaeQmD6a1EEW';

$password = $_POST['pass'];

// i stg 4dm1nh4x0r u better not be using some weak bs
// if this check blocks u, change ur dang password!
$denylists = array('.banned.1.txt', '.banned.2.txt');
foreach ($denylists as $fname) {
    $handle = @fopen($fname, "r");
    while ($handle && !feof($handle)) {
        $line = fgets($handle);
        if(strpos($line, $password) !== FALSE) {
            fclose($handle);
            echo "Access denied!";
            die();
        }
    }
    fclose($handle);
}

if (!password_verify($password, $admin_passhash)) {
    echo "Access denied!";
    die();
}

$bin_dir = $_SERVER['DOCUMENT_ROOT'] . '/../bins';

switch ($_POST['cmd']) {
case 'list_payloads':
    passthru('ls -la ' . $bin_dir);
    break;
case 'inspect_payload':
    passthru('cat ' . escapeshellarg($bin_dir . '/' . $_POST['filename']));
    break;
case 'add_payload':
    // TODO: make it easier to set up new payloads
    echo "TODO";
    break;
default:
    die();
}

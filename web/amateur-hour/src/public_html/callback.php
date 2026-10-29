<?php

$cmd = $_SERVER['DOCUMENT_ROOT'] . '/../ingest';
$user = escapeshellarg($_GET['user']);
$pass = escapeshellarg($_GET['pass']);
$host = escapeshellarg($_GET['host']);
$uname = escapeshellarg($_GET['uname']);

passthru($cmd . ' ' . $user . ' ' . $pass . ' ' . $host . ' ' . $uname . ' >&2')

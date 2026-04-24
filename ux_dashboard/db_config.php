<?php
$host = 'localhost';
$user = 'root';
$password = '';
$database = 'ux_feedback_db';

$conn = new mysqli($host, $user, $password, $database);
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}
?>
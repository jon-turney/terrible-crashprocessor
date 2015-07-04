<?php

$uploads_dir = "/home/dronecode/uploads";

// Check for no files, multiple files, upload errors
foreach($_FILES as $key => $value) {
  if ((!isset($value['error'])) ||
      (is_array($value['error'])) ||
      ($value['error'] != UPLOAD_ERR_OK)) {
    http_response_code(400);
    return;
  }
}

// No minidump file, no use to us
if (!array_key_exists('upload_file_minidump', $_FILES)) {
    http_response_code(400);
    return;
}

// Generate an id for this upload
// $id = sha1_file($_FILES['upload_file_minidump']['tmp_name']);
// XXX: terrible, use something which is properly serialized
$id = 1 + intval(file_get_contents("$uploads_dir/id"));
file_put_contents("$uploads_dir/id", $id);
$id = sprintf('%08d', $id);

if (!mkdir("$uploads_dir/$id", 0777, true)) {
  http_response_code(400);
  return;
}

// Capture all the POST data, a timestamp and source IP as JSON
$json = $_POST;
$json["UploadTime"] = time();
$json["RemoteAddr"] = getenv("REMOTE_ADDR");

$fp=fopen("$uploads_dir/$id/$id.json", "w");
fputs($fp, json_encode($json));
fclose($fp);

// Capture uploaded minidump and logfiles
foreach($_FILES as $key => $value) {
  $ext = pathinfo($value['name'], PATHINFO_EXTENSION);
  $tmp_name = $value["tmp_name"];
  move_uploaded_file($tmp_name, "$uploads_dir/$id/$id.$ext");
  // XXX: and compress?
}

echo "ccr-" . $id;

?>

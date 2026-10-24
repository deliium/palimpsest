extends RefCounted

const HttpClient := preload("res://scripts/net/http_client.gd")


func run() -> Array:
	var failures: Array = []
	_expect(failures, _shapes(), "response shapes")
	_expect(failures, _errors(), "error mapping")
	_expect(failures, _headers(), "credential headers")
	return failures


func _bytes(text: String) -> PackedByteArray:
	return text.to_utf8_buffer()


func _shapes() -> String:
	var object_body := HttpClient.parse_success(_bytes("{}"), "object")
	if not str(object_body["reason_code"]).is_empty() or typeof(object_body["value"]) != TYPE_DICTIONARY:
		return "object body rejected"
	var array_body := HttpClient.parse_success(_bytes("[1,2]"), "array")
	if not str(array_body["reason_code"]).is_empty() or typeof(array_body["value"]) != TYPE_ARRAY:
		return "array body rejected"
	var object_waiting_array := HttpClient.parse_success(_bytes("{}"), "array")
	if str(object_waiting_array["reason_code"]) != "invalid_json":
		return "object accepted as array"
	var array_waiting_object := HttpClient.parse_success(_bytes("[]"), "object")
	if str(array_waiting_object["reason_code"]) != "invalid_json":
		return "array accepted as object"
	var scalar := HttpClient.parse_success(_bytes("42"), "object")
	if str(scalar["reason_code"]) != "invalid_json":
		return "scalar accepted"
	var malformed := HttpClient.parse_success(_bytes("{"), "object")
	if str(malformed["reason_code"]) != "invalid_json":
		return "malformed JSON accepted"
	var availability := HttpClient.parse_success(_bytes('{"schema_version":"lineage-availability-v1"}'), "object")
	if not str(availability["reason_code"]).is_empty():
		return "200 availability envelope rejected"
	return ""


func _errors() -> String:
	var body := _bytes('{"code":"lineage_disabled","detail":"secret detail"}')
	if HttpClient.error_reason(401, body) != "unauthorized":
		return "401 mapping"
	if HttpClient.error_reason(403, body) != "forbidden":
		return "403 mapping"
	if HttpClient.error_reason(404, body) != "not_found":
		return "404 mapping"
	if HttpClient.error_reason(409, body) != "cursor_ahead":
		return "409 mapping"
	if HttpClient.error_reason(410, body) != "gone":
		return "410 mapping"
	if HttpClient.error_reason(503, body) != "lineage_disabled":
		return "503 safe code missing"
	if HttpClient.error_reason(503, _bytes("{}")) != "http_503":
		return "503 fallback missing"
	var unsafe := HttpClient.error_reason(400, _bytes('{"code":"Bad Code!"}'))
	if unsafe != "http_400":
		return "unsafe code forwarded"
	var scalar_error := HttpClient.error_reason(500, _bytes('"raw"'))
	if scalar_error != "http_500":
		return "scalar error forwarded"
	if HttpClient.safe_error_code(_bytes('{"code":"' + "x".repeat(200) + '"}')) != "":
		return "oversize code forwarded"
	return ""


func _headers() -> String:
	var with_token := HttpClient.build_headers("secret-token")
	if with_token.size() != 2 or not with_token[1].begins_with("x-palimpsest-token: "):
		return "token header missing"
	var without_token := HttpClient.build_headers("")
	if without_token.size() != 1:
		return "empty token should not add a header"
	for value in with_token:
		if value.contains("?") or value.contains("token="):
			return "credential leaked into query"
	return ""


func _expect(failures: Array, result: String, label: String) -> void:
	if not result.is_empty():
		failures.append("%s: %s" % [label, result])

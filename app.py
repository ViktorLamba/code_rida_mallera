from flask import Flask, render_template, request

from reed_muller import (
    ReedMullerError,
    decode_recursive,
    distance,
    encode,
    flip_positions,
    format_bits,
    message_from_codeword,
    parameters,
    parse_bits,
)


app = Flask(__name__)


DEFAULT_R = 1
DEFAULT_M = 3


def text_to_bits(text):
    return [
        int(bit)
        for byte in text.encode("utf-8")
        for bit in f"{byte:08b}"
    ]


def bits_to_text(bits):
    usable_length = len(bits) - len(bits) % 8
    if usable_length == 0:
        return ""

    raw_bytes = bytes(
        int("".join(str(bit) for bit in bits[index : index + 8]), 2)
        for index in range(0, usable_length, 8)
    )
    return raw_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")


def pad_to_block(bits, block_length):
    padding = (-len(bits)) % block_length
    return bits + [0] * padding, padding


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "r": DEFAULT_R,
        "m": DEFAULT_M,
        "message": "1011",
        "message_format": "bits",
        "received": "",
        "error_positions": "3",
        "mode": "encode",
    }

    try:
        if request.method == "POST":
            context.update(
                {
                    "r": int(request.form.get("r", DEFAULT_R)),
                    "m": int(request.form.get("m", DEFAULT_M)),
                    "message": request.form.get("message", ""),
                    "message_format": request.form.get("message_format", "bits"),
                    "received": request.form.get("received", ""),
                    "error_positions": request.form.get("error_positions", ""),
                    "mode": request.form.get("mode", "encode"),
                }
            )

        params = parameters(context["r"], context["m"])
        if params["m"] > 8:
            raise ReedMullerError("В демо-интерфейсе поддерживается m <= 8.")

        context["params"] = params

        if request.method == "POST":
            if context["mode"] == "encode":
                if context["message_format"] == "text":
                    raw_message = text_to_bits(context["message"])
                    message, padding = pad_to_block(raw_message, params["k"])
                    message_blocks = [
                        message[index : index + params["k"]]
                        for index in range(0, len(message), params["k"])
                    ]
                else:
                    message = parse_bits(context["message"], params["k"], "message")
                    raw_message = message
                    padding = 0
                    message_blocks = [message]

                codeword_blocks = [
                    encode(block, params["r"], params["m"])
                    for block in message_blocks
                ]
                codeword = [
                    bit
                    for block in codeword_blocks
                    for bit in block
                ]
                transmitted = list(codeword)
                positions = []
                if context["error_positions"].strip():
                    transmitted, positions = flip_positions(codeword, context["error_positions"])
                transmitted_blocks = [
                    transmitted[index : index + params["n"]]
                    for index in range(0, len(transmitted), params["n"])
                ]
                decoded_blocks = [
                    decode_recursive(block, params["r"], params["m"])
                    for block in transmitted_blocks
                ]
                decoded = [
                    bit
                    for block in decoded_blocks
                    for bit in block
                ]
                decoded_message = [
                    bit
                    for block in decoded_blocks
                    for bit in message_from_codeword(block, params["r"], params["m"])
                ]
                decoded_payload = decoded_message[: len(raw_message)]

                context["result"] = {
                    "message": format_bits(message, params["k"]),
                    "codeword": format_bits(codeword, params["n"]),
                    "transmitted": format_bits(transmitted, params["n"]),
                    "decoded": format_bits(decoded, params["n"]),
                    "decoded_message": format_bits(decoded_message, params["k"]),
                    "decoded_text": bits_to_text(decoded_payload) if context["message_format"] == "text" else "",
                    "padding": padding,
                    "distance": distance(codeword, transmitted),
                    "decoder_changes": distance(transmitted, decoded),
                    "positions": positions,
                }
            else:
                received = parse_bits(context["received"], params["n"], "received")
                decoded = decode_recursive(received, params["r"], params["m"])
                decoded_message = message_from_codeword(decoded, params["r"], params["m"])
                context["result"] = {
                    "received": format_bits(received),
                    "decoded": format_bits(decoded),
                    "decoded_message": format_bits(decoded_message),
                    "decoder_changes": distance(received, decoded),
                }

    except (ReedMullerError, ValueError) as exc:
        context["error"] = str(exc)
        try:
            context["params"] = parameters(context["r"], context["m"])
        except ReedMullerError:
            context["params"] = parameters(DEFAULT_R, DEFAULT_M)

    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(port=8000,debug=True)

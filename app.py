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


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "r": DEFAULT_R,
        "m": DEFAULT_M,
        "message": "1011",
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
                message = parse_bits(context["message"], params["k"], "message")
                codeword = encode(message, params["r"], params["m"])
                transmitted = codeword
                positions = []
                if context["error_positions"].strip():
                    transmitted, positions = flip_positions(codeword, context["error_positions"])
                decoded = decode_recursive(transmitted, params["r"], params["m"])
                decoded_message = message_from_codeword(decoded, params["r"], params["m"])

                context["result"] = {
                    "message": format_bits(message),
                    "codeword": format_bits(codeword),
                    "transmitted": format_bits(transmitted),
                    "decoded": format_bits(decoded),
                    "decoded_message": format_bits(decoded_message),
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

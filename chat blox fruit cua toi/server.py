import json
import os
import base64
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")


# =========================
# DATABASE
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "users": [],
            "messages": {},
            "friend_requests": []
        }
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "users": [],
            "messages": {},
            "friend_requests": []
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# RESPONSE
# =========================

def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

    handler.wfile.write(body)


def read_json(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))

        if length <= 0:
            return {}

        raw = handler.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    except Exception:
        return {}


# =========================
# HELPERS
# =========================

def find_user(data, username):
    username = str(username).strip().lower()

    for user in data["users"]:
        if user["username"].lower() == username:
            return user

    return None


def public_user(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "displayName": user.get("displayName", user["username"]),
        "avatar": user.get("avatar", ""),
        "bio": user.get("bio", ""),
        "friends": user.get("friends", [])
    }


def make_id():
    import time
    import random

    return str(int(time.time() * 1000)) + str(random.randint(100, 999))


def get_messages(data, channel):
    if channel not in data["messages"]:
        data["messages"][channel] = []

    return data["messages"][channel]


# =========================
# HTTP SERVER
# =========================

class BloxFruitHandler(SimpleHTTPRequestHandler):

    # ---------------------
    # OPTIONS
    # ---------------------

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )
        self.end_headers()

    # ---------------------
    # GET
    # ---------------------

    def do_GET(self):

        parsed = urlparse(self.path)
        path = parsed.path

        # =================
        # USERS
        # =================

        if path == "/api/users":

            data = load_data()

            users = [
                public_user(user)
                for user in data["users"]
            ]

            send_json(self, {
                "success": True,
                "users": users
            })

            return

        # =================
        # MESSAGES
        # =================

        if path == "/api/messages":

            query = parsed.query

            channel = "truyen-thong"

            for part in query.split("&"):
                if part.startswith("channel="):
                    channel = part.split("=", 1)[1]

            data = load_data()

            messages = get_messages(data, channel)

            send_json(self, {
                "success": True,
                "messages": messages
            })

            return

        # =================
        # FRIEND REQUESTS
        # =================

        if path == "/api/friend-requests":

            data = load_data()

            username = self.headers.get(
                "X-Username",
                ""
            ).strip()

            requests = []

            for request in data["friend_requests"]:

                if request["to"].lower() == username.lower():
                    requests.append(request)

            send_json(self, {
                "success": True,
                "requests": requests
            })

            return

        # =================
        # INDEX.HTML
        # =================

        if path == "/":
            self.path = "/index.html"

        return super().do_GET()

    # ---------------------
    # POST
    # ---------------------

    def do_POST(self):

        parsed = urlparse(self.path)
        path = parsed.path

        body = read_json(self)
        data = load_data()

        # =========================
        # REGISTER
        # =========================

        if path == "/api/register":

            username = str(
                body.get("username", "")
            ).strip()

            password = str(
                body.get("password", "")
            )

            display_name = str(
                body.get("displayName", username)
            ).strip()

            if not username or not password:
                send_json(self, {
                    "success": False,
                    "message": "Vui lòng nhập tài khoản và mật khẩu."
                }, 400)

                return

            if find_user(data, username):
                send_json(self, {
                    "success": False,
                    "message": "Tên tài khoản đã tồn tại."
                }, 400)

                return

            user = {
                "id": make_id(),
                "username": username,
                "password": password,
                "displayName": display_name or username,
                "avatar": "",
                "bio": "",
                "friends": []
            }

            data["users"].append(user)

            save_data(data)

            send_json(self, {
                "success": True,
                "user": public_user(user)
            })

            return

        # =========================
        # LOGIN
        # =========================

        if path == "/api/login":

            username = str(
                body.get("username", "")
            ).strip()

            password = str(
                body.get("password", "")
            )

            user = find_user(data, username)

            if not user:
                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy tài khoản."
                }, 401)

                return

            if user.get("password") != password:
                send_json(self, {
                    "success": False,
                    "message": "Mật khẩu không đúng."
                }, 401)

                return

            send_json(self, {
                "success": True,
                "user": public_user(user)
            })

            return

        # =========================
        # SEND MESSAGE
        # =========================

        if path == "/api/messages":

            channel = str(
                body.get("channel", "truyen-thong")
            )

            username = str(
                body.get("username", "")
            )

            content = str(
                body.get("content", "")
            ).strip()

            image = body.get("image", "")
            sticker = body.get("sticker", "")

            if not username:
                send_json(self, {
                    "success": False,
                    "message": "Thiếu username."
                }, 400)

                return

            if not content and not image and not sticker:
                send_json(self, {
                    "success": False,
                    "message": "Tin nhắn trống."
                }, 400)

                return

            message = {
                "id": make_id(),
                "username": username,
                "content": content,
                "image": image,
                "sticker": sticker,
                "time": __import__("datetime").datetime.now().strftime(
                    "%H:%M"
                )
            }

            messages = get_messages(data, channel)

            messages.append(message)

            # Giữ tối đa 500 tin nhắn mỗi kênh
            if len(messages) > 500:
                data["messages"][channel] = messages[-500:]

            save_data(data)

            send_json(self, {
                "success": True,
                "message": message
            })

            return

        # =========================
        # ADD FRIEND
        # =========================

        if path == "/api/friends/add":

            from_username = str(
                body.get("from", "")
            ).strip()

            to_username = str(
                body.get("to", "")
            ).strip()

            if not from_username or not to_username:
                send_json(self, {
                    "success": False,
                    "message": "Thiếu thông tin."
                }, 400)

                return

            if from_username.lower() == to_username.lower():
                send_json(self, {
                    "success": False,
                    "message": "Không thể tự kết bạn với chính mình."
                }, 400)

                return

            sender = find_user(data, from_username)
            receiver = find_user(data, to_username)

            if not sender or not receiver:
                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy người dùng."
                }, 404)

                return

            if receiver["id"] in sender.get("friends", []):
                send_json(self, {
                    "success": False,
                    "message": "Hai người đã là bạn."
                }, 400)

                return

            for request in data["friend_requests"]:

                if (
                    request["from"].lower() == from_username.lower()
                    and
                    request["to"].lower() == to_username.lower()
                ):
                    send_json(self, {
                        "success": False,
                        "message": "Đã gửi lời mời trước đó."
                    }, 400)

                    return

            request = {
                "id": make_id(),
                "from": from_username,
                "to": to_username
            }

            data["friend_requests"].append(request)

            save_data(data)

            send_json(self, {
                "success": True,
                "message": "Đã gửi lời mời kết bạn."
            })

            return

        # =========================
        # ACCEPT FRIEND
        # =========================

        if path == "/api/friends/accept":

            request_id = str(
                body.get("requestId", "")
            )

            request = None

            for r in data["friend_requests"]:
                if r["id"] == request_id:
                    request = r
                    break

            if not request:
                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy lời mời."
                }, 404)

                return

            sender = find_user(
                data,
                request["from"]
            )

            receiver = find_user(
                data,
                request["to"]
            )

            if not sender or not receiver:
                send_json(self, {
                    "success": False,
                    "message": "Người dùng không tồn tại."
                }, 404)

                return

            if receiver["id"] not in sender["friends"]:
                sender["friends"].append(
                    receiver["id"]
                )

            if sender["id"] not in receiver["friends"]:
                receiver["friends"].append(
                    sender["id"]
                )

            data["friend_requests"].remove(request)

            save_data(data)

            send_json(self, {
                "success": True,
                "message": "Đã chấp nhận kết bạn."
            })

            return

        # =========================
        # REJECT FRIEND
        # =========================

        if path == "/api/friends/reject":

            request_id = str(
                body.get("requestId", "")
            )

            before = len(data["friend_requests"])

            data["friend_requests"] = [
                r for r in data["friend_requests"]
                if r["id"] != request_id
            ]

            if len(data["friend_requests"]) == before:

                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy lời mời."
                }, 404)

                return

            save_data(data)

            send_json(self, {
                "success": True,
                "message": "Đã từ chối lời mời."
            })

            return

        # =========================
        # REMOVE FRIEND
        # =========================

        if path == "/api/friends/remove":

            username = str(
                body.get("username", "")
            )

            friend_username = str(
                body.get("friend", "")
            )

            user = find_user(
                data,
                username
            )

            friend = find_user(
                data,
                friend_username
            )

            if not user or not friend:

                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy người dùng."
                }, 404)

                return

            user["friends"] = [
                x for x in user.get("friends", [])
                if x != friend["id"]
            ]

            friend["friends"] = [
                x for x in friend.get("friends", [])
                if x != user["id"]
            ]

            save_data(data)

            send_json(self, {
                "success": True,
                "message": "Đã xóa bạn."
            })

            return

        # =========================
        # UPDATE PROFILE
        # =========================

        if path == "/api/profile":

            username = str(
                body.get("username", "")
            )

            user = find_user(
                data,
                username
            )

            if not user:

                send_json(self, {
                    "success": False,
                    "message": "Không tìm thấy tài khoản."
                }, 404)

                return

            if "displayName" in body:
                user["displayName"] = str(
                    body["displayName"]
                ).strip()

            if "bio" in body:
                user["bio"] = str(
                    body["bio"]
                )

            if "avatar" in body:
                avatar = str(
                    body["avatar"]
                )

                # Giới hạn avatar để data.json không quá lớn
                if len(avatar) <= 2_000_000:
                    user["avatar"] = avatar

            save_data(data)

            send_json(self, {
                "success": True,
                "user": public_user(user)
            })

            return

        # =========================
        # NOT FOUND
        # =========================

        send_json(self, {
            "success": False,
            "message": "API không tồn tại: " + path
        }, 404)


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    print("")
    print("==============================")
    print(" Blox Fruits Vietnam Server")
    print("==============================")
    print("")
    print("Local:")
    print("http://localhost:8000")
    print("")
    print("Server dang chay...")
    print("Nhan Ctrl + C de dung server.")
    print("")

    server = ThreadingHTTPServer(
        (HOST, PORT),
        BloxFruitHandler
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("")
        print("Dang dung server...")

    finally:
        server.server_close()
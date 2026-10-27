from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
from core.database import get_conn, init_db, export_to_csv, get_monthly_report, get_frequent_items
from core.utils import expiry_status, generate_chart_base64
from core.ai import ask_gemini, ask_offline

def render_html(search_query="", edit_id=None):
    conn = get_conn()
    refresh_tag = ""  # Auto-refresh removed to stop form clearing

    if search_query:
        search_query = search_query.strip()
        items = conn.execute("SELECT * FROM items WHERE LOWER(name) LIKE ?", (f"%{search_query.lower()}%",)).fetchall()
    else:
        items = conn.execute("SELECT * FROM items ORDER BY name").fetchall()
    
    edit_item = None
    if edit_id:
        edit_item = conn.execute("SELECT * FROM items WHERE id = ?", (edit_id,)).fetchone()
    conn.close()

    total_items = len(items)
    expiring = sum(1 for i in items if i["expiry_date"] and expiry_status(i["expiry_date"])[1] in ["orange", "red"])
    report = get_monthly_report()
    frequent = get_frequent_items()
    chart_img = generate_chart_base64()

    rows = ""
    for i in items:
        label, color = expiry_status(i["expiry_date"])
        rows += f"""
        <tr>
            <td>{i['name']}</td>
            <td>{i['category']}</td>
            <td>{i['quantity']} {i['unit'] or ''}</td>
            <td>₹{i['price']}</td>
            <td>{i['expiry_date'] or '—'}</td>
            <td class="{color}">{label}</td>
            <td>
                <a href="/?edit={i['id']}" style="color:#f59e0b; text-decoration:none; margin-right:8px;">✏️ Edit</a>
                <a href="/delete/{i['id']}" style="color:#ef4444; text-decoration:none;" onclick="return confirm('Delete?')">❌ Del</a>
            </td>
        </tr>
        """

    edit_form_html = ""
    if edit_item:
        edit_form_html = f"""
        <div class="box" style="width: 100%; background: #334155;">
            <h3>✏️ Edit Item: {edit_item['name']}</h3>
            <form method="POST" action="/update_item">
                <input type="hidden" name="id" value="{edit_item['id']}">
                <input type="text" name="name" value="{edit_item['name']}" required>
                <input type="text" name="category" value="{edit_item['category']}" required>
                <input type="number" step="0.01" name="qty" value="{edit_item['quantity']}" required>
                <input type="number" step="0.01" name="price" value="{edit_item['price']}" required>
                <input type="text" name="expiry" value="{edit_item['expiry_date'] or ''}" placeholder="YYYY-MM-DD (optional)">
                <button type="submit" style="background:#f59e0b;">Save Changes</button>
            </form>
        </div>
        """

    freq_rows = "".join([f"<li>{f['item_name']} (x{f['n']})</li>" for f in frequent])
    cat_rows = "".join([f"<li>{c['category']}: ₹{c['s']}</li>" for c in report['by_cat']])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>FoodWise Pro Dashboard</title>
        {refresh_tag}
        <style>
            body {{ font-family: sans-serif; background: #0f172a; color: white; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 20px; }}
            .stats {{ display: flex; gap: 20px; justify-content: center; margin-bottom: 30px; }}
            .card {{ background: #1e293b; padding: 20px; border-radius: 10px; width: 180px; text-align: center; border-left: 4px solid #10B981; }}
            .card h2 {{ margin: 0; color: #10B981; }}
            .container {{ display: flex; gap: 20px; flex-wrap: wrap; }}
            .box {{ background: #1e293b; padding: 20px; border-radius: 10px; width: 48%; margin-bottom: 20px; }}
            input, select {{ padding: 8px; width: 100%; margin: 5px 0; border-radius: 5px; border: none; box-sizing: border-box; }}
            button {{ padding: 10px; background: #10B981; color: white; border: none; border-radius: 5px; width: 100%; cursor: pointer; margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; }}
            th {{ background: #0f172a; color: #94a3b8; }}
            .green {{ color: #10B981; }} .orange {{ color: #f59e0b; }} .red {{ color: #ef4444; }} .gray {{ color: #64748b; }}
            .search-bar {{ display: flex; gap: 10px; margin-bottom: 20px; }}
            .search-bar input {{ width: 300px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🍎 FoodWise Pro Dashboard</h1>
            <a href="/export" style="color: #10B981;">📥 Export CSV</a>
        </div>

        <div class="search-bar">
            <form method="GET" action="/">
                <input type="text" name="q" placeholder="🔍 Search items..." value="{search_query}">
                <button type="submit" style="width: auto; padding: 8px 20px;">Search</button>
            </form>
        </div>

        <div class="stats">
            <div class="card"><h2>{total_items}</h2><p>Total Items</p></div>
            <div class="card" style="border-color: #f59e0b;"><h2 style="color: #f59e0b;">{expiring}</h2><p>Expiring/Expired</p></div>
            <div class="card" style="border-color: #3B82F6;"><h2 style="color: #3B82F6;">₹{report['total']}</h2><p>This Month Spend</p></div>
        </div>

        {edit_form_html}

        <div class="container">
            <div class="box">
                <h3>➕ Add Item</h3>
                <form method="POST" action="/add_item">
                    <input type="text" name="name" placeholder="Name (e.g. Milk)" required>
                    <input type="text" name="category" placeholder="Category (e.g. Dairy)" required>
                    <input type="number" step="0.01" name="qty" placeholder="Quantity" required>
                    <input type="number" step="0.01" name="price" placeholder="Price" required>
                    <input type="text" name="expiry" placeholder="Expiry (YYYY-MM-DD) optional">
                    <button type="submit">Add Item</button>
                </form>
            </div>

            <div class="box">
                <h3>🛒 Record Purchase</h3>
                <form method="POST" action="/record_purchase">
                    <input type="text" name="name" placeholder="Item Name" required>
                    <input type="number" step="0.01" name="qty" placeholder="Quantity" required>
                    <input type="number" step="0.01" name="price" placeholder="Price" required>
                    <button type="submit">Record Purchase</button>
                </form>
            </div>

            <div class="box">
                <h3>📈 Monthly Report</h3>
                <p>Total Spend: <b>₹{report['total']}</b></p>
                <h4>Spend by Category:</h4>
                <ul>{cat_rows if cat_rows else "<li>No data</li>"}</ul>
                <h4>Frequent Items:</h4>
                <ul>{freq_rows if freq_rows else "<li>No data</li>"}</ul>
            </div>

            <div class="box">
                <h3>📊 Stock Chart</h3>
                {"<img src='data:image/png;base64," + chart_img + "' style='width:100%'>" if chart_img else "<p>No data</p>"}
            </div>
        </div>

        <table>
            <tr><th>Name</th><th>Category</th><th>Qty</th><th>Price</th><th>Expiry</th><th>Status</th><th>Action</th></tr>
            {rows if rows else "<tr><td colspan='7'>No items found.</td></tr>"}
        </table>
        
        <div class="box" style="width: 100%; margin-top: 20px;">
            <h3>🤖 Ask AI</h3>
            <input type="text" id="q" placeholder="e.g. What's expiring?">
            <button onclick="ask()">Ask AI</button>
            <p id="ans" style="margin-top: 10px; color: #10B981;"></p>
        </div>

        <script>
        function ask() {{
            let q = document.getElementById("q").value;
            document.getElementById("ans").innerText = "Thinking...";
            fetch("/api/ai", {{
                method: "POST", headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{question: q}})
            }})
            .then(r => r.json())
            .then(d => {{ 
                if (d.error) {{
                    document.getElementById("ans").innerText = "Error: " + d.error;
                }} else {{
                    document.getElementById("ans").innerText = d.answer; 
                }}
            }});
        }}
        </script>
    </body>
    </html>
    """
    return html.encode("utf-8")

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            params = parse_qs(parsed.query)
            search_q = params.get("q", [""])[0]
            edit_id = params.get("edit", [None])[0]
            content = render_html(search_q, edit_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == "/export":
            filename = export_to_csv("exported_data.csv")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Exported to {filename}".encode())
        elif parsed.path.startswith("/delete/"):
            item_id = int(parsed.path.split("/")[-1])
            conn = get_conn()
            conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            conn.commit(); conn.close()
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if self.path == "/add_item":
            form = parse_qs(body.decode())
            name, cat = form.get("name", [""])[0], form.get("category", [""])[0]
            qty, price = float(form.get("qty", ["0"])[0]), float(form.get("price", ["0"])[0])
            exp = form.get("expiry", [""])[0] or None
            conn = get_conn()
            conn.execute("INSERT INTO items (name, category, quantity, unit, price, expiry_date, added_date) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, cat, qty, "pcs", price, exp, "2026-10-26"))
            conn.commit(); conn.close()
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()

        elif self.path == "/update_item":
            form = parse_qs(body.decode())
            item_id = int(form.get("id", ["0"])[0])
            name, cat = form.get("name", [""])[0], form.get("category", [""])[0]
            qty, price = float(form.get("qty", ["0"])[0]), float(form.get("price", ["0"])[0])
            exp = form.get("expiry", [""])[0] or None
            conn = get_conn()
            conn.execute("UPDATE items SET name=?, category=?, quantity=?, price=?, expiry_date=? WHERE id=?", (name, cat, qty, price, exp, item_id))
            conn.commit(); conn.close()
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()

        elif self.path == "/record_purchase":
            form = parse_qs(body.decode())
            name, qty, price = form.get("name", [""])[0], float(form.get("qty", ["0"])[0]), float(form.get("price", ["0"])[0])
            conn = get_conn()
            conn.execute("INSERT INTO purchases (item_name, category, quantity, price, purchase_date) VALUES (?, ?, ?, ?, ?)", (name, "Other", qty, price, "2026-10-26"))
            conn.commit(); conn.close()
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()

        elif self.path == "/api/ai":
            data = json.loads(body)
            question = data.get("question", "")
            ans, err = ask_gemini(question)
            if err: 
                print(f"⚠️ Gemini Error: {err}")
                ans = ask_offline(question)
                mode = "offline"
            else:
                mode = "online"
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"answer": ans, "mode": mode, "error": err}).encode())

    def log_message(self, format, *args):
        pass

def run_server(port=8000):
    init_db()
    server = HTTPServer(("127.0.0.1", port), RequestHandler)
    print(f"\n🚀 Dashboard running at http://localhost:{port}\n")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
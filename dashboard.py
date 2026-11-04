import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from core.database import get_conn, init_db, export_to_csv, get_monthly_report, get_frequent_items
from core.utils import expiry_status, generate_chart_base64
from core.ai import ask_gemini, ask_offline, load_api_key

UNITS = ["pcs", "kg", "g", "L", "ml", "pack", "dozen"]

def item_exists(name):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM items WHERE LOWER(name) = LOWER(?)", (name.strip(),)).fetchone()
    conn.close()
    return existing is not None

def render_html(search_query="", edit_id=None, error_msg=""):
    conn = get_conn()
    
    if search_query:
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

    has_key = load_api_key() is not None
    ai_status_badge = '<span class="badge badge-green">🟢 API Connected</span>' if has_key else '<span class="badge badge-orange">🟡 Offline</span>'

    rows = ""
    for i in items:
        label, color = expiry_status(i["expiry_date"])
        rows += f"""
        <tr>
            <td style="font-weight: 600; color: #FFFFFF;">{i['name']}</td>
            <td><span class="badge badge-purple">{i['category']}</span></td>
            <td>{i['quantity']} {i['unit'] or ''}</td>
            <td style="font-weight: 600; color: #A78BFA;">₹{i['price']}</td>
            <td>{i['expiry_date'] or '—'}</td>
            <td class="{color}">{label}</td>
            <td>
                <a href="/?edit={i['id']}" class="btn-action edit">✏️</a>
                <a href="/delete/{i['id']}" class="btn-action delete" onclick="return confirm('Are you sure?')">❌</a>
            </td>
        </tr>
        """

    unit_options_add = "".join([f'<option value="{u}">{u}</option>' for u in UNITS])
    
    edit_form_html = ""
    if edit_item:
        unit_options_edit = "".join([f'<option value="{u}" {"selected" if edit_item["unit"] == u else ""}>{u}</option>' for u in UNITS])
        edit_form_html = f"""
        <div class="card edit-card">
            <h3 style="color: #FCD34D;">✏️ Edit Item: {edit_item['name']}</h3>
            <form method="POST" action="/update_item" class="grid-form">
                <input type="hidden" name="id" value="{edit_item['id']}">
                <input type="text" name="name" value="{edit_item['name']}" required placeholder="Name">
                <input type="text" name="category" value="{edit_item['category']}" required placeholder="Category">
                <input type="number" step="0.01" name="qty" value="{edit_item['quantity']}" required placeholder="Quantity">
                <select name="unit" required>{unit_options_edit}</select>
                <input type="number" step="0.01" name="price" value="{edit_item['price']}" required placeholder="Price">
                <input type="text" name="expiry" value="{edit_item['expiry_date'] or ''}" placeholder="Expiry (YYYY-MM-DD)">
                <button type="submit" class="btn-warning">Update Item</button>
            </form>
        </div>
        """

    freq_rows = "".join([f"<li>{f['item_name']} <span class='badge badge-purple'>{f['n']}x</span></li>" for f in frequent])
    cat_rows = "".join([f"<li>{c['category']} <span class='badge badge-purple'>₹{c['s']}</span></li>" for c in report['by_cat']])
    error_html = f'<div style="background: rgba(239, 68, 68, 0.2); color: #FCA5A5; padding: 12px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #EF4444; font-weight: 600;">{error_msg}</div>' if error_msg else ''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FoodWise Pro</title>
        <style>
            /* PREMIUM VIBRANT THEME */
            :root {{
                --bg-main: #0F0C29;
                --bg-card: rgba(255, 255, 255, 0.05); /* Glass effect */
                --text-main: #FFFFFF;
                --text-muted: #C4B5FD;
                --accent: #8B5CF6; /* Vibrant Purple */
                --accent-hover: #A78BFA;
                --border: rgba(255, 255, 255, 0.1);
            }}

            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }}
            
            body {{ 
                /* Gorgeous Gradient Background */
                background: linear-gradient(135deg, #0F0C29 0%, #302B63 50%, #24243E 100%);
                color: var(--text-main); 
                display: flex; 
                min-height: 100vh; 
                background-attachment: fixed;
            }}
            
            /* Glass Sidebar */
            .sidebar {{ 
                width: 260px; 
                background: rgba(15, 12, 41, 0.7); 
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border-right: 1px solid var(--border); 
                padding: 24px; 
                display: flex; 
                flex-direction: column; 
                gap: 10px; 
                position: fixed; 
                height: 100vh; 
            }}
            .logo {{ 
                font-size: 24px; 
                font-weight: 800; 
                color: #FFFFFF; 
                margin-bottom: 32px; 
                display: flex; 
                align-items: center; 
                gap: 10px; 
                text-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
            }}
            .logo span {{ color: var(--accent); }}
            
            .nav-link {{ 
                color: var(--text-muted); 
                text-decoration: none; 
                padding: 12px 16px; 
                border-radius: 12px; 
                transition: all 0.3s ease; 
                font-size: 15px;
                font-weight: 500;
            }}
            .nav-link:hover {{ 
                background: rgba(255, 255, 255, 0.1); 
                color: #FFFFFF; 
                transform: translateX(5px);
            }}
            .nav-link.active {{ 
                background: linear-gradient(90deg, var(--accent) 0%, rgba(139, 92, 246, 0.1) 100%);
                color: #FFFFFF; 
                box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);
            }}

            /* Main Content */
            .main-content {{ margin-left: 260px; padding: 40px; width: calc(100% - 260px); }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }}
            .header h1 {{ font-size: 28px; font-weight: 700; color: #FFFFFF; }}
            
            .btn-export {{ 
                background: var(--accent); 
                border: none; 
                color: #FFFFFF; 
                padding: 12px 20px; 
                border-radius: 12px; 
                text-decoration: none; 
                font-weight: 600; 
                font-size: 14px;
                transition: all 0.3s ease; 
                box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
            }}
            .btn-export:hover {{ 
                background: var(--accent-hover); 
                transform: translateY(-2px);
            }}

            /* Shining Stat Cards */
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; margin-bottom: 40px; }}
            .stat-card {{ 
                background: var(--bg-card); 
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                padding: 24px; 
                border-radius: 20px; 
                border: 1px solid var(--border); 
                position: relative;
                overflow: hidden;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                transition: transform 0.3s ease;
            }}
            .stat-card:hover {{ transform: translateY(-5px); }}
            
            /* Shining gradients for cards */
            .stat-card.glow-purple::before {{
                content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
                background: radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 60%);
            }}
            .stat-card.glow-pink::before {{
                content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
                background: radial-gradient(circle, rgba(236, 72, 153, 0.2) 0%, transparent 60%);
            }}
            .stat-card.glow-blue::before {{
                content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
                background: radial-gradient(circle, rgba(59, 130, 246, 0.2) 0%, transparent 60%);
            }}

            .stat-card h2 {{ font-size: 38px; font-weight: 800; margin-bottom: 4px; color: #FFFFFF; position: relative; z-index: 1; }}
            .stat-card p {{ color: var(--text-muted); font-size: 14px; font-weight: 600; letter-spacing: 0.5px; position: relative; z-index: 1; }}

            /* Glass Cards */
            .layout-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
            .card {{ 
                background: var(--bg-card); 
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border-radius: 20px; 
                padding: 28px; 
                border: 1px solid var(--border); 
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            }}
            .card h3 {{ font-size: 18px; font-weight: 700; margin-bottom: 24px; color: #FFFFFF; }}
            .edit-card {{ border: 1px solid #FCD34D; box-shadow: 0 0 20px rgba(252, 211, 77, 0.2); margin-bottom: 24px; }}

            /* Forms */
            .grid-form {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
            .grid-form input, .grid-form select {{ 
                padding: 14px 16px; 
                border-radius: 12px; 
                border: 1px solid var(--border); 
                background: rgba(0, 0, 0, 0.2); 
                color: #FFFFFF; 
                outline: none; 
                width: 100%;
                font-size: 14px;
                transition: all 0.3s;
            }}
            .grid-form input:focus, .grid-form select:focus {{ 
                border-color: var(--accent); 
                background: rgba(0, 0, 0, 0.4);
                box-shadow: 0 0 15px rgba(139, 92, 246, 0.3); 
            }}
            .grid-form button {{ 
                grid-column: span 2; 
                padding: 14px; 
                border-radius: 12px; 
                border: none; 
                background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%); 
                color: #FFFFFF; 
                font-weight: 700; 
                cursor: pointer; 
                transition: all 0.3s; 
                font-size: 15px;
                margin-top: 8px;
                box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);
            }}
            .grid-form button:hover {{ 
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(139, 92, 246, 0.5);
            }}
            .btn-warning {{ background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%) !important; box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3) !important; }}

            /* Search */
            .search-form {{ display: flex; gap: 12px; margin-bottom: 24px; }}
            .search-form input {{ 
                flex: 1; 
                padding: 16px 24px; 
                border-radius: 12px; 
                border: 1px solid var(--border); 
                background: rgba(0, 0, 0, 0.2); 
                color: white; 
                outline: none; 
                font-size: 15px;
            }}
            .search-form input:focus {{ border-color: var(--accent); box-shadow: 0 0 15px rgba(139, 92, 246, 0.3); }}
            .search-form button {{ 
                padding: 0 32px; 
                border-radius: 12px; 
                border: none; 
                background: var(--bg-card); 
                color: white; 
                cursor: pointer; 
                font-weight: 600;
                border: 1px solid var(--border);
                transition: all 0.2s;
            }}
            .search-form button:hover {{ background: rgba(255, 255, 255, 0.1); }}

            /* Table */
            .table-container {{ 
                background: var(--bg-card); 
                backdrop-filter: blur(20px);
                border-radius: 20px; 
                border: 1px solid var(--border); 
                overflow: hidden; 
                margin-bottom: 32px; 
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            }}
            table {{ width: 100%; border-collapse: collapse; text-align: left; }}
            th {{ 
                background: rgba(0, 0, 0, 0.3); 
                padding: 18px 20px; 
                font-size: 13px; 
                font-weight: 700;
                text-transform: uppercase; 
                color: var(--text-muted); 
                border-bottom: 1px solid var(--border); 
                letter-spacing: 0.5px;
            }}
            td {{ padding: 18px 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-size: 15px; color: #E2E8F0; }}
            tr:last-child td {{ border-bottom: none; }}
            tr:hover {{ background: rgba(255, 255, 255, 0.03); }}
            
            .badge {{ padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; }}
            .badge-purple {{ background: rgba(139, 92, 246, 0.2); color: #C4B5FD; border: 1px solid rgba(139, 92, 246, 0.3); }}
            .badge-green {{ background: rgba(16, 185, 129, 0.2); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.3); }}
            .badge-orange {{ background: rgba(245, 158, 11, 0.2); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.3); }}
            
            .btn-action {{ text-decoration: none; font-size: 16px; margin-right: 12px; transition: 0.2s; }}
            .btn-action:hover {{ transform: scale(1.2); display: inline-block; }}

            .green {{ color: #10B981; font-weight: 600; }}
            .orange {{ color: #F59E0B; font-weight: 600; }}
            .red {{ color: #EF4444; font-weight: 600; }}
            .gray {{ color: #9CA3AF; }}

            ul {{ list-style: none; }}
            ul li {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); color: #E2E8F0; font-size: 15px; }}
            ul li:last-child {{ border-bottom: none; }}

            /* AI Chat */
            .suggestions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
            .suggestion-chip {{ 
                background: rgba(255, 255, 255, 0.05); 
                border: 1px solid var(--border); 
                color: var(--text-muted); 
                padding: 8px 16px; 
                border-radius: 20px; 
                font-size: 13px; 
                font-weight: 500;
                cursor: pointer; 
                transition: all 0.2s; 
            }}
            .suggestion-chip:hover {{ background: rgba(139, 92, 246, 0.2); color: #FFFFFF; border-color: var(--accent); }}
            
            .ai-response {{ 
                margin-top: 16px; 
                padding: 24px; 
                border-radius: 16px; 
                background: rgba(0, 0, 0, 0.3); 
                border: 1px solid var(--border); 
                color: #F8FAFC; 
                display: none; 
                white-space: pre-wrap; 
                font-size: 15px;
                line-height: 1.6;
                backdrop-filter: blur(10px);
            }}
            
            .mode-select {{ 
                padding: 10px 16px; 
                border-radius: 10px; 
                border: 1px solid var(--border); 
                background: rgba(0, 0, 0, 0.4); 
                color: var(--accent-hover); 
                font-weight: 700; 
                font-size: 13px;
                outline: none; 
                cursor: pointer; 
            }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="logo">🍎 FoodWise<span>Pro</span></div>
            <a href="/" class="nav-link active">📊 Dashboard</a>
            <a href="#add-item" class="nav-link">➕ Add Item</a>
            <a href="#record-purchase" class="nav-link">🛒 Purchases</a>
            <a href="#ask-ai" class="nav-link">🤖 AI Assistant</a>
        </div>

        <div class="main-content">
            <div class="header">
                <h1>Overview</h1>
                <a href="/export" class="btn-export">📥 Export CSV</a>
            </div>

            <div class="stats-grid">
                <div class="stat-card glow-purple">
                    <h2>{total_items}</h2>
                    <p>Total Items</p>
                </div>
                <div class="stat-card glow-pink">
                    <h2 style="color: #F472B6;">{expiring}</h2>
                    <p>Expiring / Expired</p>
                </div>
                <div class="stat-card glow-blue">
                    <h2 style="color: #60A5FA;">₹{report['total']}</h2>
                    <p>Month Spend</p>
                </div>
            </div>

            <form method="GET" action="/" class="search-form">
                <input type="text" name="q" placeholder="Search items by name..." value="{search_query}">
                <button type="submit">Search</button>
            </form>

            <div class="table-container">
                <table>
                    <thead><tr><th>Name</th><th>Category</th><th>Qty</th><th>Price</th><th>Expiry</th><th>Status</th><th>Actions</th></tr></thead>
                    <tbody>{rows if rows else "<tr><td colspan='7' style='text-align:center; padding: 40px; color: var(--text-muted); font-weight: 500;'>No items found. Add an item below.</td></tr>"}</tbody>
                </table>
            </div>

            {edit_form_html}

            <div class="layout-grid">
                <div class="card" id="add-item">
                    <h3>➕ Add New Item</h3>
                    {error_html}
                    <form method="POST" action="/add_item" class="grid-form">
                        <input type="text" name="name" placeholder="Item Name" required>
                        <input type="text" name="category" placeholder="Category" required>
                        <input type="number" step="0.01" name="qty" placeholder="Quantity" required>
                        <select name="unit" required>{unit_options_add}</select>
                        <input type="number" step="0.01" name="price" placeholder="Price (₹)" required style="grid-column: span 2;">
                        <input type="text" name="expiry" placeholder="Expiry (YYYY-MM-DD) Optional" style="grid-column: span 2;">
                        <button type="submit">Add to Inventory</button>
                    </form>
                </div>

                <div class="card" id="record-purchase">
                    <h3>🛒 Record Purchase</h3>
                    <form method="POST" action="/record_purchase" class="grid-form">
                        <input type="text" name="name" placeholder="Item Name" required style="grid-column: span 2;">
                        <input type="number" step="0.01" name="qty" placeholder="Quantity" required>
                        <input type="number" step="0.01" name="price" placeholder="Price (₹)" required>
                        <button type="submit">Log Purchase</button>
                    </form>
                </div>

                <div class="card">
                    <h3>📈 Monthly Report</h3>
                    <ul>{cat_rows if cat_rows else "<li>No data available</li>"}</ul>
                </div>

                <div class="card">
                    <h3>🔥 Frequently Purchased</h3>
                    <ul>{freq_rows if freq_rows else "<li>No purchases yet</li>"}</ul>
                </div>
            </div>

            <div class="card" style="margin-bottom: 32px;">
                <h3>📊 Stock by Category</h3>
                <div style="text-align: center; padding: 20px;">
                    {"<img src='data:image/png;base64," + chart_img + "' style='max-width: 100%; border-radius: 16px; filter: drop-shadow(0 0 20px rgba(139, 92, 246, 0.3));'>" if chart_img else "<p style='color: var(--text-muted);'>No data.</p>"}
                </div>
            </div>

            <div class="card" id="ask-ai" style="border: 1px solid rgba(139, 92, 246, 0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                    <h3 style="margin-bottom: 0;">🤖 Ask AI</h3>
                    <div>
                        {ai_status_badge}
                        <select id="ai_mode" class="mode-select">
                            <option value="online">🌐 Online Mode</option>
                            <option value="offline">🔌 Offline Mode</option>
                        </select>
                    </div>
                </div>
                
                <div class="suggestions">
                    <button type="button" class="suggestion-chip" onclick="setQ('What is expiring soon?')">What is expiring?</button>
                    <button type="button" class="suggestion-chip" onclick="setQ('How much did I spend this month?')">Total spend?</button>
                    <button type="button" class="suggestion-chip" onclick="setQ('What is running low in stock?')">Low stock?</button>
                    <button type="button" class="suggestion-chip" onclick="setQ('Do I have milk?')">Have milk?</button>
                </div>

                <form onsubmit="askAI(event)" class="search-form" style="margin-bottom: 0;">
                    <input type="text" id="q" placeholder="Ask anything about your groceries..." required>
                    <button type="submit">Ask AI</button>
                </form>
                <div id="ans" class="ai-response"></div>
            </div>
        </div>

        <script>
        function setQ(question) {{
            document.getElementById("q").value = question;
            askAI(new Event('submit')); 
        }}

        function askAI(e) {{
            if(e) e.preventDefault();
            let q = document.getElementById("q").value;
            let mode = document.getElementById("ai_mode").value; 
            let ansBox = document.getElementById("ans");
            
            ansBox.style.display = "block";
            ansBox.innerHTML = "<span style='color: #C4B5FD;'>Processing...</span>";
            
            fetch("/api/ai", {{
                method: "POST", 
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{question: q, mode: mode}}) 
            }})
            .then(r => r.json())
            .then(d => {{ 
                ansBox.innerHTML = d.answer; 
                if (mode === "online") {{
                    ansBox.style.borderLeft = "4px solid #10B981";
                }} else {{
                    ansBox.style.borderLeft = "4px solid #8B5CF6";
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
            error_type = params.get("error", [None])[0]
            error_msg = "⚠️ Error: This item already exists in your inventory!" if error_type == "duplicate" else ""
                
            content = render_html(search_q, edit_id, error_msg)
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
            unit = form.get("unit", ["pcs"])[0]
            exp = form.get("expiry", [""])[0] or None
            
            if item_exists(name):
                self.send_response(303)
                self.send_header('Location', '/?error=duplicate')
                self.end_headers()
                return
                
            conn = get_conn()
            conn.execute("INSERT INTO items (name, category, quantity, unit, price, expiry_date, added_date) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, cat, qty, unit, price, exp, "2026-10-26"))
            conn.commit(); conn.close()
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()

        elif self.path == "/update_item":
            form = parse_qs(body.decode())
            item_id = int(form.get("id", ["0"])[0])
            name, cat = form.get("name", [""])[0], form.get("category", [""])[0]
            qty, price = float(form.get("qty", ["0"])[0]), float(form.get("price", ["0"])[0])
            unit = form.get("unit", ["pcs"])[0]
            exp = form.get("expiry", [""])[0] or None
            conn = get_conn()
            conn.execute("UPDATE items SET name=?, category=?, quantity=?, unit=?, price=?, expiry_date=? WHERE id=?", (name, cat, qty, unit, price, exp, item_id))
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
            mode = data.get("mode", "online")
            
            if mode == "offline":
                ans = ask_offline(question)
                err = None
            else:
                ans, err = ask_gemini(question)
                if err or not ans:
                    ans = ask_offline(question)
                    mode = "offline"
            
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
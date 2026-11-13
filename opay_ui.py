from opay_script import OPAY_JS

OPAY_CSS = """
<style>
    * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; background: #0b131e; color: #f8fafc; padding: 16px; }
    .container { max-width: 920px; margin: 0 auto; }
    h1 { text-align: center; color: #00d285; margin-bottom: 16px; }
    .card { background: #131f30; border: 1px solid #1e2f47; border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .wallet-banner { background: linear-gradient(135deg, #00b875, #008f5a); color: #fff; border-radius: 16px; padding: 22px; margin-bottom: 16px; }
    .balance { font-size: 2rem; font-weight: 800; margin: 6px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    input, select, button { width: 100%; padding: 12px; margin-top: 10px; border-radius: 10px; border: 1px solid #2b3f5c; font-size: 1rem; }
    input, select { background: #0b131e; color: #f8fafc; }
    button { background: #00d285; color: #062117; font-weight: 700; border: none; cursor: pointer; }
    .btn-secondary { background: #22344d; color: #e2e8f0; }
    .tx-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #1e2f47; gap: 8px; }
    .credit { color: #00d285; font-weight: 700; }
    .debit { color: #fb7185; font-weight: 700; }
    .error { color: #fb7185; min-height: 20px; font-size: 0.9rem; }
    .success { color: #00d285; min-height: 20px; font-size: 0.9rem; }
</style>
"""

def render_opay_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NairaPay Microfinance Bank</title>{OPAY_CSS}
</head>
<body>
    <div class="container">
        <h1>🏦 NairaPay Microfinance Wallet</h1>
        <form id="authCard" class="card" style="max-width:440px;margin:20px auto;" autocomplete="off" onsubmit="return false;">
            <h2>🔐 Open or Access Account</h2>
            <input id="nameInput" autocomplete="off" placeholder="Full Name (for New Account)" />
            <input id="emailInput" type="email" autocomplete="off" placeholder="Email Address" />
            <input id="passInput" type="password" autocomplete="new-password" placeholder="Strong Password (8+ chars, A-z, 0-9, !@#)" />
            <input id="pinInput" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password" placeholder="4-Digit Transaction PIN (for New Account)" />
            <button type="button" onclick="submitAuth('/auth/login')">Log In</button>
            <button type="button" class="btn-secondary" onclick="submitAuth('/auth/register')">Create Free Bank Account</button>
            <p id="authError" class="error"></p>
        </form>

        <div id="bankArea" style="display:none;">
            <div class="wallet-banner">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <span id="holderName" style="font-weight:700;font-size:1.1rem;"></span>
                    <button class="btn-secondary" style="width:auto;margin:0;padding:8px 14px;background:rgba(0,0,0,0.25);" onclick="logout()">Log Out</button>
                </div>
                <div id="balanceText" class="balance">₦0.00</div>
                <div>Account Number: <strong id="acctNumText"></strong> (NairaPay Instant Transfer)</div>
            </div>

            <div class="grid">
                <div class="card">
                    <h3>💸 Send Money (P2P Transfer)</h3>
                    <input id="recipAcct" maxlength="10" inputmode="numeric" placeholder="Recipient 10-Digit Account (90...)" oninput="checkRecipient()" />
                    <p id="recipNamePreview" class="success" style="margin:6px 0 0;"></p>
                    <input id="sendAmount" type="number" step="0.01" min="1" placeholder="Amount (₦)" />
                    <input id="sendNote" maxlength="60" placeholder="Narration (e.g. Lunch, Rent)" />
                    <input id="sendPin" type="password" maxlength="4" inputmode="numeric" placeholder="Enter 4-Digit Transaction PIN" />
                    <button onclick="sendMoney()">Send Money Now</button>
                    <p id="sendMsg" class="error"></p>
                </div>

                <div class="card">
                    <h3>💳 Add Money & Pay Bills</h3>
                    <input id="topupAmount" type="number" step="0.01" min="1" placeholder="Top-Up Amount (₦)" />
                    <button onclick="topUpWallet()">+ Instant Wallet Top-Up</button>
                    <hr style="border-color:#1e2f47;margin:16px 0;" />
                    <select id="billService"><option value="MTN Airtime">MTN Airtime</option><option value="Airtel Data">Airtel Data</option><option value="IKEDC Electricity">IKEDC Electricity</option></select>
                    <input id="billTarget" placeholder="Phone Number or Meter Number" />
                    <input id="billAmount" type="number" step="0.01" min="1" placeholder="Bill Amount (₦)" />
                    <input id="billPin" type="password" maxlength="4" inputmode="numeric" placeholder="Enter 4-Digit PIN" />
                    <button class="btn-secondary" onclick="payUtilityBill()">Pay Bill</button>
                    <p id="billMsg" class="error"></p>
                </div>
            </div>

            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <h3 style="margin:0;">🧾 Transaction History</h3>
                    <button class="btn-secondary" style="width:auto;margin:0;padding:8px 14px;" onclick="downloadStatement()">📄 Download PDF Statement</button>
                </div>
                <div id="txList" style="margin-top:10px;"></div>
            </div>
        </div>
    </div>
    {OPAY_JS}
</body>
</html>"""

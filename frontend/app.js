/**
 * Real calls answer in milliseconds here; a real environment does not. Every
 * form waits at least one second, button disabled and a spinner shown, so the
 * page behaves as it would against a remote stack.
 */
const MIN_WAIT_MS = 1000;
const JITTER_MS = 600;

async function slowFetch(form, url, init) {
  const button = form.querySelector("button[type=submit]");
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Working";
  button.classList.add("busy");
  const pause = MIN_WAIT_MS + (crypto.getRandomValues(new Uint16Array(1))[0] % JITTER_MS);
  try {
    const [response] = await Promise.all([fetch(url, init), new Promise((r) => setTimeout(r, pause))]);
    return response;
  } finally {
    button.disabled = false;
    button.textContent = label;
    button.classList.remove("busy");
  }
}

/**
 * Sends the typed username to the API and shows the greeting it answers with.
 */
const form = document.getElementById("hello-form");
const input = document.getElementById("username");
const greeting = document.getElementById("greeting");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = new FormData(form).get("username");
  const response = await slowFetch(
    form,
    `/api/hello?username=${encodeURIComponent(username)}`,
  );
  if (!response.ok) {
    greeting.className = "result ko";
    greeting.textContent = `Error ${response.status}`;
    return;
  }
  const body = await response.json();
  greeting.className = "result ok";
  greeting.textContent = body.message;
});

/**
 * Fills the field with an example username and sends it.
 */
for (const example of document.querySelectorAll("[data-username]")) {
  example.addEventListener("click", () => {
    input.value = example.dataset.username;
    form.requestSubmit();
  });
}

const orderForm = document.getElementById("order-form");
const orderStatus = document.getElementById("order-status");
const orderSteps = document.getElementById("order-steps");
const productSelect = document.getElementById("order-product");
const POLL_INTERVAL_MS = 500;
const STEP_LABELS = {
  reserve_stock: "Reserve stock",
  issue_invoice: "Issue invoice",
  capture_payment: "Capture payment",
};

/**
 * Fills the product list from the API, with prices and stock.
 */
async function loadProducts() {
  const response = await fetch("/api/products");
  const products = await response.json();
  productSelect.replaceChildren(
    ...products.map((product) => {
      const option = document.createElement("option");
      option.value = product.sku;
      option.textContent = `${product.name} · ${(product.price_cents / 100).toFixed(2)} ${product.currency} · ${product.stock} in stock`;
      return option;
    }),
  );
}

/**
 * Shows where the workflow stands: its status, its order, its steps.
 */
function renderWorkflow(workflow) {
  orderStatus.className = "result";
  orderStatus.innerHTML = "";
  const status = document.createElement("span");
  status.className = `pill ${workflow.status}`;
  status.textContent = `workflow ${workflow.status}`;
  const order = document.createElement("span");
  order.className = `pill ${workflow.order_status}`;
  order.textContent = `order #${workflow.order_id} ${workflow.order_status}`;
  orderStatus.append(status, " ", order);
  orderSteps.replaceChildren(
    ...workflow.steps.map((step) => {
      const item = document.createElement("li");
      item.className = step.status;
      const dot = document.createElement("span");
      dot.className = "dot";
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = `${STEP_LABELS[step.name] ?? step.name} · ${step.status}`;
      const detail = document.createElement("div");
      detail.className = "detail";
      detail.textContent = step.detail ?? "";
      item.append(dot, name, detail);
      return item;
    }),
  );
}

/**
 * Asks the API how the workflow is going until it is over.
 */
async function follow(workflowId) {
  const response = await fetch(`/api/orders/workflows/${workflowId}`);
  const workflow = await response.json();
  renderWorkflow(workflow);
  if (workflow.status === "running") {
    setTimeout(() => follow(workflowId), POLL_INTERVAL_MS);
  } else {
    loadProducts();
  }
}

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(orderForm);
  orderSteps.replaceChildren();
  const response = await slowFetch(orderForm, "/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: data.get("username"),
      sku: data.get("sku"),
      quantity: Number(data.get("quantity")),
    }),
  });
  if (response.status !== 202) {
    const body = await response.json();
    orderStatus.className = "result ko";
    orderStatus.textContent = `Error ${response.status}: ${typeof body.detail === "string" ? body.detail : "invalid order"}`;
    return;
  }
  const accepted = await response.json();
  follow(accepted.workflow_id);
});

/**
 * Fills the order form with an example and places it.
 */
for (const example of document.querySelectorAll("[data-order]")) {
  example.addEventListener("click", () => {
    const [username, sku] = example.dataset.order.split(":");
    document.getElementById("order-username").value = username;
    productSelect.value = sku;
    document.getElementById("order-quantity").value = 1;
    orderForm.requestSubmit();
  });
}

const MAILBOX_URL = "http://localhost:8025";
const accountStatus = document.getElementById("account-status");
const tabs = document.querySelectorAll("[data-tab]");
const panels = document.querySelectorAll("[data-panel]");
const codeForm = document.getElementById("code-form");
let mfaToken = "";
const ticket = new URLSearchParams(window.location.search).get("ticket");

/**
 * Shows one account form and hides the others.
 */
function showTab(name) {
  for (const tab of tabs) {
    tab.setAttribute("aria-selected", String(tab.dataset.tab === name));
  }
  for (const panel of panels) {
    panel.hidden = panel.dataset.panel !== name;
  }
  codeForm.hidden = true;
}

/**
 * Writes the answer of the identity API under the account forms.
 */
function tellAccount(kind, text, withMailbox = false) {
  accountStatus.className = `result ${kind}`;
  accountStatus.textContent = text;
  if (withMailbox) {
    const link = document.createElement("a");
    link.href = MAILBOX_URL;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open the QA mailbox";
    accountStatus.append(" ", link);
  }
}

/**
 * Posts a form to the identity API and returns the status and the body.
 */
async function callIdentity(form, path, body) {
  const response = await slowFetch(form, `/api/identity/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  const json = text ? JSON.parse(text) : {};
  const detail = typeof json.detail === "string" ? json.detail : "invalid input";
  return { status: response.status, json, detail };
}

for (const tab of tabs) {
  tab.addEventListener("click", () => showTab(tab.dataset.tab));
}

document.getElementById("signin-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.target);
  codeForm.hidden = true;
  const answer = await callIdentity(event.target, "login", {
    email: data.get("email"),
    password: data.get("password"),
  });
  if (answer.status === 403 && answer.json.detail === "mfa_required") {
    mfaToken = answer.json.mfa_token;
    codeForm.hidden = false;
    tellAccount("info", "Password right: enter the code of your authenticator app.");
    document.getElementById("code-input").focus();
  } else if (answer.status === 200) {
    tellAccount("ok", `Signed in as ${answer.json.email} (${answer.json.user_id}).`);
  } else {
    tellAccount("ko", `Error ${answer.status}: ${answer.detail}`, answer.status === 423);
  }
});

codeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = await callIdentity(event.target, "mfa/verify", {
    mfa_token: mfaToken,
    code: new FormData(event.target).get("code"),
  });
  if (answer.status === 200) {
    codeForm.hidden = true;
    tellAccount("ok", `Signed in as ${answer.json.email} (${answer.json.user_id}).`);
  } else {
    tellAccount("ko", `Error ${answer.status}: ${answer.detail}`);
  }
});

/**
 * Computes the current TOTP code of a base32 secret (RFC 6238), as a test does.
 */
async function totpCode(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...secret].map((c) => alphabet.indexOf(c).toString(2).padStart(5, "0")).join("");
  const key = new Uint8Array(Math.floor(bits.length / 8)).map((_, i) => parseInt(bits.slice(i * 8, i * 8 + 8), 2));
  const counter = new DataView(new ArrayBuffer(8));
  counter.setUint32(4, Math.floor(Date.now() / 1000 / 30));
  const hmacKey = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const digest = new Uint8Array(await crypto.subtle.sign("HMAC", hmacKey, counter.buffer));
  const offset = digest[19] & 0x0f;
  const number = new DataView(digest.buffer).getUint32(offset) & 0x7fffffff;
  return String(number % 1000000).padStart(6, "0");
}

document.querySelector("[data-totp]").addEventListener("click", async (event) => {
  document.getElementById("code-input").value = await totpCode(event.target.dataset.totp);
});

document.getElementById("signup-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = await callIdentity(event.target, "signup", {
    email: new FormData(event.target).get("email"),
  });
  if (answer.status === 201) {
    tellAccount("info", `Account ${answer.json.email} created: open the welcome email to choose a password.`, true);
  } else {
    tellAccount("ko", `Error ${answer.status}: ${answer.detail}`);
  }
});

document.getElementById("reset-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = await callIdentity(event.target, "password-reset", {
    email: new FormData(event.target).get("email"),
  });
  tellAccount(answer.status === 202 ? "info" : "ko", answer.detail, answer.status === 202);
});

document.getElementById("password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = await callIdentity(event.target, "password", {
    ticket,
    password: new FormData(event.target).get("password"),
  });
  if (answer.status === 204) {
    tellAccount("ok", "Password set: you can sign in now.");
    window.history.replaceState(null, "", "/#account");
    document.querySelector('[data-tab="password"]').hidden = true;
    showTab("signin");
  } else {
    tellAccount("ko", `Error ${answer.status}: ${answer.detail}`);
  }
});

/**
 * Fills the sign-in form with an example account and submits it.
 */
for (const example of document.querySelectorAll("[data-signin]")) {
  example.addEventListener("click", () => {
    const [email, password] = example.dataset.signin.split(":");
    document.getElementById("signin-email").value = email;
    document.getElementById("signin-password").value = password;
    document.getElementById("signin-form").requestSubmit();
  });
}

document.querySelector("[data-signup]").addEventListener("click", () => {
  const tag = crypto.randomUUID().slice(0, 8);
  document.getElementById("signup-email").value = `qa-mailbox+${tag}@mycompany.test`;
});

const PRODUCTS = ["welcome", "checkout", "account"];

/**
 * Shows the product the address names, alone, or the list of products when it
 * names none. A password link opens the account access.
 */
function route() {
  const wanted = ticket ? "account" : window.location.hash.slice(1);
  const product = PRODUCTS.includes(wanted) ? wanted : null;
  document.getElementById("home").hidden = product !== null;
  for (const name of PRODUCTS) {
    document.getElementById(name).hidden = name !== product;
  }
  for (const link of document.querySelectorAll("nav[aria-label=Products] a")) {
    if (link.getAttribute("href") === `#${product ?? ""}`) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();

if (ticket) {
  document.querySelector('[data-tab="password"]').hidden = false;
  showTab("password");
  tellAccount("info", "Choose the password of your account.");
}

loadProducts();

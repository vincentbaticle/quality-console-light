/**
 * Baseline load of the customer welcome: GET /api/hello through the storefront.
 *
 * Ten virtual customers greet themselves for half a minute, each call going
 * through nginx, the API, MySQL, the Bank Partner and Redis. The thresholds
 * are the service level the product promises: under 1% of failed calls, 95%
 * of the greetings in less than 500 ms.
 *
 * handleSummary writes what the results bucket reads: summary.json (the
 * metrics the console's Details tab shows) and junit.xml (one test case per
 * threshold, carrying the test metadata as properties, like a pytest run).
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const REPORTS = __ENV.REPORTS_DIR || "reports/perf";

/** Customers of the seed: two with a balance, one without bank account. */
const USERNAMES = ["ada", "grace", "zoe"];

/** Who the test belongs to, the same fields as metadata_test(...) in pytest. */
const METADATA = {
  system: "storefront",
  product: "customer-welcome",
  business_capability: "engage",
  component: "hello-api",
  group: "qa-core",
  testing_scope: "performance",
  tags: "k6",
};

export const options = {
  stages: [
    { duration: "5s", target: 10 },
    { duration: "20s", target: 10 },
    { duration: "5s", target: 0 },
  ],
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    checks: ["rate>0.99"],
  },
};

export default function () {
  const username = USERNAMES[Math.floor(Math.random() * USERNAMES.length)];
  const response = http.get(`${BASE_URL}/api/hello?username=${username}`, {
    tags: { name: "GET /api/hello" },
  });
  check(response, {
    "answers 200": (r) => r.status === 200,
    "greets by first name": (r) => r.json("message").startsWith("Hello "),
  });
  sleep(0.2);
}

/** The metrics flattened the way the results bucket reads them, a rate as its value. */
function flatSummary(data) {
  const metrics = {};
  for (const [name, metric] of Object.entries(data.metrics)) {
    const value = metric.type === "rate" ? { value: metric.values.rate } : {};
    metrics[name] = { ...metric.values, ...value, thresholds: metric.thresholds || {} };
  }
  return JSON.stringify({ metrics }, null, 2);
}

const escapeXml = (text) =>
  String(text).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c]);

/** One JUnit test case per threshold, failed when the threshold broke. */
function junit(data) {
  const properties = Object.entries(METADATA)
    .map(([name, value]) => `<property name="${name}" value="${escapeXml(value)}"/>`)
    .join("");
  const cases = [];
  for (const [name, metric] of Object.entries(data.metrics)) {
    for (const [threshold, verdict] of Object.entries(metric.thresholds || {})) {
      const failure = verdict.ok ? "" : `<failure message="${escapeXml(`${name} broke ${threshold}`)}"/>`;
      cases.push(
        `<testcase classname="perf.customer_welcome_baseline" name="${escapeXml(`${name} ${threshold}`)}" time="0">` +
          `<properties>${properties}</properties>${failure}</testcase>`,
      );
    }
  }
  const failures = cases.filter((c) => c.includes("<failure")).length;
  return (
    '<?xml version="1.0" encoding="utf-8"?><testsuites>' +
    `<testsuite name="k6" tests="${cases.length}" failures="${failures}">${cases.join("")}</testsuite></testsuites>`
  );
}

export function handleSummary(data) {
  const requests = data.metrics.http_reqs.values;
  const p95 = data.metrics.http_req_duration.values["p(95)"];
  return {
    [`${REPORTS}/summary.json`]: flatSummary(data),
    [`${REPORTS}/junit.xml`]: junit(data),
    stdout: `[k6] ${requests.count} requests, ${requests.rate.toFixed(1)}/s, p95 ${p95.toFixed(1)} ms\n`,
  };
}

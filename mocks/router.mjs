/**
 * Contract mocks: every OpenAPI contract of /contracts served by Prism behind
 * one port. /<name>/... goes to the Prism started for
 * contracts/<name>-openapi.yaml, / lists the mocks. A contract published in
 * contracts/ is a mock, with nothing else to write.
 */
import { spawn } from 'node:child_process';
import { readdirSync } from 'node:fs';
import http from 'node:http';

const CONTRACTS = process.env.CONTRACTS_DIR ?? '/contracts';
const PORT = Number(process.env.PORT ?? 4010);
const FIRST_PRISM_PORT = 4100;
const SUFFIX = '-openapi.yaml';

const mocks = readdirSync(CONTRACTS)
  .filter(file => file.endsWith(SUFFIX))
  .sort()
  .map((file, index) => ({
    name: file.slice(0, -SUFFIX.length),
    contract: `contracts/${file}`,
    port: FIRST_PRISM_PORT + index,
    ready: false,
  }));

for (const mock of mocks) {
  const prism = spawn(
    'prism',
    ['mock', '-m', 'false', '-h', '127.0.0.1', '-p', String(mock.port), `${CONTRACTS}/${mock.name}${SUFFIX}`],
    { stdio: ['ignore', 'inherit', 'inherit'] },
  );
  prism.on('exit', code => console.error(`prism for ${mock.name} exited with ${code}`));
  waitFor(mock);
}

/** Waits until the Prism of a mock answers, whatever it answers. */
function waitFor(mock) {
  const probe = http.get({ host: '127.0.0.1', port: mock.port, path: '/' }, answer => {
    answer.resume();
    mock.ready = true;
    if (mocks.every(m => m.ready)) console.log(`mocks ready: ${mocks.map(m => m.name).join(', ')}`);
  });
  probe.on('error', () => setTimeout(() => waitFor(mock), 500));
}

/** Lists the mocks, 200 once every one answers, 503 before. */
function list(response) {
  const ready = mocks.every(m => m.ready);
  response.writeHead(ready ? 200 : 503, { 'content-type': 'application/json' });
  response.end(
    JSON.stringify(
      {
        ready,
        mocks: mocks.map(({ name, contract, ready }) => ({ name, contract, path: `/${name}/`, ready })),
      },
      null,
      2,
    ),
  );
}

http
  .createServer((request, response) => {
    const url = new URL(request.url, 'http://mocks');
    const [, name, ...rest] = url.pathname.split('/');
    if (!name) return list(response);
    const mock = mocks.find(m => m.name === name);
    if (!mock) {
      response.writeHead(404, { 'content-type': 'application/json' });
      return response.end(JSON.stringify({ detail: `No mock named ${name}: see /` }));
    }
    const upstream = http.request(
      {
        host: '127.0.0.1',
        port: mock.port,
        method: request.method,
        path: `/${rest.join('/')}${url.search}`,
        headers: request.headers,
      },
      answer => {
        response.writeHead(answer.statusCode ?? 502, answer.headers);
        answer.pipe(response);
      },
    );
    upstream.on('error', () => {
      response.writeHead(503, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ detail: `The mock ${name} is still starting` }));
    });
    request.pipe(upstream);
  })
  .listen(PORT, () => console.log(`mocks listening on :${PORT}`));

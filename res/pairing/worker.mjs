const headers = { 'Cache-Control': 'no-store' };
const json = (body, status = 200) => Response.json(body, { status, headers });

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (request.method === 'GET' && path === '/health') return json({ status: 'ok' });
    const enrolling = request.method === 'POST' && path === '/v1/hosts';
    const listing = request.method === 'GET' && path === '/v1/hosts';
    const removing = request.method === 'DELETE' && /^\/v1\/hosts\/[a-f0-9]{64}$/.test(path);
    if (!enrolling && !listing && !removing) return json({ error: 'Not found' }, 404);
    const token = enrolling || removing ? env.ENROLL_TOKEN : env.CONTROLLER_TOKEN;
    if (!token || request.headers.get('Authorization') !== ('Bearer ' + token)) {
      return json({ error: 'Unauthorized' }, 401);
    }
    try {
      if (removing) {
        await env.DB.prepare('DELETE FROM hosts WHERE device_key = ?')
          .bind(path.split('/').pop()).run();
        return json({ removed: true });
      }
      if (listing) {
        const { results } = await env.DB.prepare(
          'SELECT id, name, platform, last_seen FROM hosts ORDER BY name LIMIT 200'
        ).all();
        return json({ hosts: results, server_time: Date.now() });
      }
      const text = await request.text();
      if (text.length > 2048) return json({ error: 'Request too large' }, 413);
      const host = JSON.parse(text);
      if (typeof host.id !== 'string' || !/^[0-9]{6,16}$/.test(host.id) ||
          typeof host.device_key !== 'string' || !/^[a-f0-9]{64}$/.test(host.device_key) ||
          typeof host.name !== 'string' || host.name.length < 1 || host.name.length > 128 ||
          !['windows', 'linux'].includes(host.platform)) {
        return json({ error: 'Invalid host' }, 400);
      }
      await env.DB.prepare(
        'INSERT INTO hosts (device_key, id, name, platform, last_seen) VALUES (?, ?, ?, ?, ?) ' +
        'ON CONFLICT(device_key) DO UPDATE SET id=excluded.id, name=excluded.name, ' +
        'platform=excluded.platform, last_seen=excluded.last_seen'
      ).bind(host.device_key, host.id, host.name, host.platform, Date.now()).run();
      return json({ registered: true });
    } catch (_) {
      return json({ error: 'Pairing request failed' }, 500);
    }
  },
};

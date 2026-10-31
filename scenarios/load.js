// Background load for the scenarios: a steady stream of votes, each from its own client id
// (so vote-api's per-client rate limit never kicks in). No thresholds: errors are the point.
import http from 'k6/http';

export const options = {
  scenarios: {
    votes: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 100),
      timeUnit: '1s',
      duration: __ENV.DURATION || '10m',
      preAllocatedVUs: 50,
      maxVUs: 300,
    },
  },
};

export default function () {
  const option = Math.random() < 0.5 ? 'cat' : 'dog';
  http.post(`${__ENV.BASE_URL}/api/vote`, JSON.stringify({ option }), {
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': `load-${__VU}-${__ITER}-${Date.now()}` },
    timeout: '10s',
  });
}

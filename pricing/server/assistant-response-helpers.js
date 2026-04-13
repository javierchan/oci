'use strict';

function buildServiceUnavailableMessage(userText) {
  const source = String(userText || '').trim();
  return [
    'This OCI pricing guidance service is not available for that request right now.',
    source ? `I could not interpret \`${source}\` safely with the current GenAI controller and structured pricing context.` : 'I could not interpret the request safely with the current GenAI controller and structured pricing context.',
    'I prefer to stop here rather than return an unreliable answer or quote.',
  ].join('\n\n');
}

module.exports = {
  buildServiceUnavailableMessage,
};

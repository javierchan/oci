'use strict';

function isGreeting(text) {
  return /^(hola|hello|hi|hey|buenas|good morning|good afternoon|good evening)\b[!. ]*$/i.test(String(text || '').trim());
}

function isFastConnectText(text) {
  return /\bfast\s*connect\b|\bfastconnect\b/i.test(String(text || ''));
}

function conversationMentionsFastConnect(conversation) {
  return (conversation || []).some((item) => isFastConnectText(item.content || ''));
}

function isConfidenceQuestion(text) {
  return /\b(estas seguro|estás seguro|seguro de ese precio|are you sure|is that price correct|is that accurate)\b/i.test(String(text || ''));
}

function parseRegionAnswer(text) {
  const source = String(text || '').trim().toLowerCase();
  if (!source) return null;
  if (/quer[eé]taro/.test(source)) return { code: 'mx-queretaro-1', label: 'Mexico Central (Queretaro)' };
  if (/monterrey/.test(source)) return { code: 'mx-monterrey-1', label: 'Mexico Northeast (Monterrey)' };
  return null;
}

function buildEarlyAssistantReply({ conversation, userText } = {}) {
  if (isGreeting(userText)) {
    return {
      ok: true,
      mode: 'answer',
      message: 'Hola. Puedo ayudarte a cotizar servicios de OCI, comparar SKUs, explicar pricing o estimar un Excel. Si quieres una cotización directa, dime el producto y las variables clave como cantidad, horas, OCPU/ECPU, storage o bandwidth.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  if (conversationMentionsFastConnect(conversation) && isConfidenceQuestion(userText)) {
    return {
      ok: true,
      mode: 'answer',
      message: 'Sí para el cargo base del puerto. En OCI, el precio de FastConnect para el puerto es uniforme entre regiones, así que la región no cambia esa cotización base. Si quieres, puedo ayudarte a revisar además otros cargos relacionados, como conectividad adicional o tráfico de salida, pero el puerto de 1 Gbps sigue siendo el mismo.',
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  const explicitRegion = parseRegionAnswer(userText);
  if (conversationMentionsFastConnect(conversation) && explicitRegion) {
    return {
      ok: true,
      mode: 'answer',
      message: `${explicitRegion.label} es una región válida de OCI (${explicitRegion.code}). Para FastConnect, el precio base del puerto no cambia por región, así que la cotización del puerto se mantiene. Si quieres, el siguiente paso es revisar si en tu caso hay cargos adicionales asociados al diseño de conectividad.`,
      intent: { intent: 'answer', shouldQuote: false, needsClarification: false },
    };
  }

  return null;
}

module.exports = {
  isGreeting,
  isFastConnectText,
  conversationMentionsFastConnect,
  isConfidenceQuestion,
  parseRegionAnswer,
  buildEarlyAssistantReply,
};

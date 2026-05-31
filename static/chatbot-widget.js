/**
 * AMICANA Chatbot Widget — Ianna
 * Envía mensajes al proxy FastAPI POST /chatbot (que reenvía a n8n).
 *
 * Uso:
 *   <script src="/static/chatbot-widget.js"
 *           data-webhook="/chatbot">   <!-- URL relativa al servidor -->
 *   </script>
 *
 * Si data-webhook no se especifica, usa /chatbot por defecto.
 */

(function () {
  "use strict";

  // ── Configuración ──────────────────────────────────────────────────────────

  const DEFAULT_WEBHOOK = "/chatbot";
  const TIMEOUT_MS = 15000;
  const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 días

  function getWebhookUrl() {
    const script = document.currentScript ||
      document.querySelector('script[data-webhook]');
    return (script && script.dataset.webhook) ||
      window.AMICANA_CHAT_WEBHOOK ||
      DEFAULT_WEBHOOK;
  }

  const WEBHOOK_URL = getWebhookUrl();

  // ── Session ID — localStorage con TTL 7 días ───────────────────────────────

  function getSessionId() {
    const KEY = "amicana_session";
    try {
      const stored = localStorage.getItem(KEY);
      if (stored) {
        const obj = JSON.parse(stored);
        if (obj && obj.id && (Date.now() - (obj.createdAt || 0)) < SESSION_TTL_MS) {
          return obj.id;
        }
      }
    } catch (_) {}
    const id = "sess_" + Date.now() + "_" + Math.random().toString(36).slice(2, 9);
    try {
      localStorage.setItem(KEY, JSON.stringify({ id, createdAt: Date.now() }));
    } catch (_) {}
    return id;
  }

  // ── JWT del alumno (pre-auth 5.2) ─────────────────────────────────────────

  function getUserToken() {
    try {
      return sessionStorage.getItem("amicana_token") ||
             localStorage.getItem("amicana_token") || null;
    } catch (_) {
      return null;
    }
  }

  // ── HTML del widget ────────────────────────────────────────────────────────

  function buildWidget() {
    const root = document.createElement("div");
    root.id = "amicana-chat-bubble";
    root.innerHTML = `
      <div id="amicana-chat-panel" role="dialog" aria-label="Ianna — Asistente AMICANA">
        <div id="amicana-chat-header">
          <div class="avatar" aria-hidden="true">I</div>
          <div class="info">
            <div class="name">Ianna</div>
            <div class="subtitle">Asistente virtual de AMICANA</div>
          </div>
          <button id="amicana-faq-toggle" aria-label="Preguntas frecuentes"
                  title="Preguntas frecuentes"
                  style="background:none;border:none;cursor:pointer;color:#fff;padding:4px 8px;font-size:13px;opacity:.85;">
            FAQ
          </button>
        </div>
        <div id="amicana-faq-panel" style="display:none;padding:8px 12px;background:#f1f5f9;border-bottom:1px solid #e2e8f0;max-height:160px;overflow-y:auto;"></div>
        <div id="amicana-chat-messages" aria-live="polite"></div>
        <div id="amicana-chat-input-area">
          <textarea id="amicana-chat-input" rows="1"
            placeholder="Escribí tu consulta..." aria-label="Mensaje"></textarea>
          <button id="amicana-chat-send" aria-label="Enviar" disabled>
            <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
      <button id="amicana-chat-toggle" aria-label="Abrir chat">
        <svg class="icon-chat" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/>
        </svg>
        <svg class="icon-close" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <line x1="18" y1="6" x2="6" y2="18" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
          <line x1="6" y1="6" x2="18" y2="18" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
      </button>
    `;
    document.body.appendChild(root);
  }

  // ── Mensajes ───────────────────────────────────────────────────────────────

  function scrollToBottom() {
    const container = document.getElementById("amicana-chat-messages");
    if (container) container.scrollTop = container.scrollHeight;
  }

  function addMessage(role, content) {
    const container = document.getElementById("amicana-chat-messages");
    const wrapper = document.createElement("div");
    wrapper.className = "amicana-msg " + role;

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (typeof content === "string") {
      bubble.textContent = content;
    } else {
      if (content.text) {
        const txt = document.createElement("div");
        txt.textContent = content.text;
        bubble.appendChild(txt);
      }
      if (content.qr_url) {
        const img = document.createElement("img");
        img.src = content.qr_url;
        img.alt = "QR de pago";
        img.className = "qr-img";
        bubble.appendChild(img);
      }
      if (content.pdf_url) {
        const link = document.createElement("a");
        link.href = content.pdf_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "pdf-link";
        link.textContent = "Descargar comprobante PDF";
        bubble.appendChild(link);
      }
    }

    wrapper.appendChild(bubble);
    container.appendChild(wrapper);
    scrollToBottom();
    return wrapper;
  }

  // 5.5 — bubble de error con botón Reintentar
  function addErrorBubble(lastText) {
    const container = document.getElementById("amicana-chat-messages");
    const wrapper = document.createElement("div");
    wrapper.className = "amicana-msg bot amicana-error-bubble";
    wrapper.innerHTML = `
      <div class="bubble" style="background:#fee2e2;color:#991b1b;">
        No se pudo conectar. ¿Querés volver a intentarlo?
        <br>
        <button class="amicana-retry-btn"
                style="margin-top:6px;padding:4px 12px;background:#ef4444;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">
          Reintentar
        </button>
      </div>`;
    container.appendChild(wrapper);
    scrollToBottom();
    const btn = wrapper.querySelector(".amicana-retry-btn");
    if (btn && lastText) {
      btn.addEventListener("click", () => {
        wrapper.remove();
        sendMessage(lastText);
      });
    }
    return wrapper;
  }

  function addTypingIndicator() {
    const container = document.getElementById("amicana-chat-messages");
    const wrapper = document.createElement("div");
    wrapper.className = "amicana-msg bot amicana-typing";
    wrapper.id = "amicana-typing-indicator";
    wrapper.innerHTML = `<div class="bubble"><div class="amicana-typing-dots"><span></span><span></span><span></span></div></div>`;
    container.appendChild(wrapper);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const el = document.getElementById("amicana-typing-indicator");
    if (el) el.remove();
  }

  // ── Normalizar respuesta del webhook (5.3) ────────────────────────────────

  function normalizeResponse(data) {
    if (typeof data === "string") return { text: data };
    if (data.text || data.qr_url || data.pdf_url) return data;
    // Formato LangChain n8n: {output: "..." | {text,qr_url,pdf_url}}
    if (data.output !== undefined) {
      if (typeof data.output === "string") return { text: data.output };
      if (typeof data.output === "object" && data.output !== null) {
        return { text: data.output.text, qr_url: data.output.qr_url, pdf_url: data.output.pdf_url };
      }
    }
    if (data.message) return { text: data.message };
    return { text: "Respuesta recibida, pero no pude interpretarla." };
  }

  // ── FAQ visual (5.7) ──────────────────────────────────────────────────────

  let _faqLoaded = false;

  async function loadFaq() {
    if (_faqLoaded) return;
    const panel = document.getElementById("amicana-faq-panel");
    if (!panel) return;
    try {
      const r = await fetch("/chatbot/faq");
      if (!r.ok) return;
      const d = await r.json();
      const items = (d.data && d.data.faq) || d.faq || [];
      panel.innerHTML = "";
      if (!items.length) { panel.textContent = "Sin preguntas frecuentes."; return; }
      const label = document.createElement("p");
      label.style.cssText = "margin:0 0 6px;font-size:11px;color:#64748b;font-weight:600;";
      label.textContent = "Preguntas frecuentes — hacé click para enviar";
      panel.appendChild(label);
      const chips = document.createElement("div");
      chips.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;";
      items.forEach(item => {
        const chip = document.createElement("button");
        chip.className = "amicana-faq-chip";
        chip.style.cssText = "background:#e0f2fe;color:#0369a1;border:none;border-radius:12px;padding:4px 10px;font-size:12px;cursor:pointer;";
        chip.textContent = item.q;
        chip.addEventListener("click", () => {
          document.getElementById("amicana-faq-panel").style.display = "none";
          _faqLoaded = false;
          sendMessage(item.q);
        });
        chips.appendChild(chip);
      });
      panel.appendChild(chips);
      _faqLoaded = true;
    } catch (_) {}
  }

  function bindFaqToggle() {
    const btn = document.getElementById("amicana-faq-toggle");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const panel = document.getElementById("amicana-faq-panel");
      if (!panel) return;
      const showing = panel.style.display !== "none";
      panel.style.display = showing ? "none" : "block";
      if (!showing) await loadFaq();
    });
  }

  // ── Mensaje de bienvenida (5.4) ───────────────────────────────────────────

  async function loadWelcomeMessage() {
    try {
      const r = await fetch("/chatbot/welcome");
      if (!r.ok) return null;
      const d = await r.json();
      return (d.data && d.data.texto) || d.texto || null;
    } catch (_) {
      return null;
    }
  }

  // ── Envío al webhook ───────────────────────────────────────────────────────

  let sending = false;
  let _lastMessage = null;

  async function sendMessage(text) {
    if (sending || !text.trim()) return;
    if (!WEBHOOK_URL) {
      addMessage("bot", "El chatbot no está configurado todavía. Contactá al administrador.");
      return;
    }

    _lastMessage = text;
    sending = true;
    setSendEnabled(false);

    addMessage("user", text);
    addTypingIndicator();

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    // Headers — incluye JWT si está disponible (5.2)
    const headers = { "Content-Type": "application/json" };
    const userToken = getUserToken();
    if (userToken) headers["X-User-Token"] = userToken;

    try {
      const res = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: getSessionId(),
          message: text,
        }),
        signal: controller.signal,
      });

      clearTimeout(timer);
      removeTypingIndicator();

      if (res.status === 429) {
        addMessage("bot", "Demasiados mensajes. Esperá un momento antes de continuar.");
        return;
      }

      if (!res.ok) {
        addErrorBubble(_lastMessage);
        return;
      }

      const data = await res.json();
      const normalized = normalizeResponse(data);
      addMessage("bot", normalized);

    } catch (err) {
      clearTimeout(timer);
      removeTypingIndicator();
      if (err.name !== "AbortError") {
        console.error("[AMICANA chat]", err);
      }
      addErrorBubble(_lastMessage);
    } finally {
      sending = false;
      setSendEnabled(true);
      focusInput();
    }
  }

  // ── Input ──────────────────────────────────────────────────────────────────

  function setSendEnabled(enabled) {
    const btn = document.getElementById("amicana-chat-send");
    if (btn) btn.disabled = !enabled;
  }

  function focusInput() {
    const input = document.getElementById("amicana-chat-input");
    if (input) input.focus();
  }

  function autoResize(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 80) + "px";
  }

  function bindInputEvents() {
    const input = document.getElementById("amicana-chat-input");
    const sendBtn = document.getElementById("amicana-chat-send");

    input.addEventListener("input", function () {
      autoResize(this);
      setSendEnabled(this.value.trim().length > 0 && !sending);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const val = this.value.trim();
        if (val) {
          this.value = "";
          autoResize(this);
          setSendEnabled(false);
          sendMessage(val);
        }
      }
    });

    sendBtn.addEventListener("click", function () {
      const val = input.value.trim();
      if (val) {
        input.value = "";
        autoResize(input);
        setSendEnabled(false);
        sendMessage(val);
      }
    });
  }

  // ── Toggle ─────────────────────────────────────────────────────────────────

  let opened = false;

  async function togglePanel() {
    const root = document.getElementById("amicana-chat-bubble");
    opened = !opened;
    root.classList.toggle("open", opened);

    if (opened) {
      const messages = document.getElementById("amicana-chat-messages");
      if (!messages.hasChildNodes()) {
        // 5.4 — bienvenida desde endpoint, con fallback hardcodeado
        const welcomeText = await loadWelcomeMessage();
        addMessage("bot", welcomeText ||
          "Hola, soy Ianna, la asistente virtual de AMICANA.\n" +
          "Puedo ayudarte con:\n" +
          "  - Consultar el estado de tus cuotas\n" +
          "  - Pagar una cuota\n" +
          "  - Información sobre cursos y modalidades\n" +
          "  - Asesorarte sobre exámenes internacionales (ECECE, TOEIC, TOEFL)\n" +
          "¿En qué te puedo ayudar?");
      }
      focusInput();
    }
  }

  function bindToggle() {
    const btn = document.getElementById("amicana-chat-toggle");
    btn.addEventListener("click", togglePanel);
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    buildWidget();
    bindToggle();
    bindInputEvents();
    bindFaqToggle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

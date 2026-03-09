const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const loading = document.getElementById("loading");
const endpoint = "/chat";

window.addEventListener("DOMContentLoaded", () => {
  addMessage("Hi Favour \uD83D\uDC4B I'm your birthday AI assistant.", "bot");
  input.focus();
});

function addMessage(text, sender) {
  const bubble = document.createElement("div");
  bubble.className = `message ${sender}`;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

function setLoading(isLoading) {
  loading.classList.toggle("active", isLoading);
  loading.setAttribute("aria-hidden", String(!isLoading));
}

async function sendMessage(text) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail || "Unknown error.";
    throw new Error(detail);
  }

  const data = await response.json();
  return data.reply;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";
  setLoading(true);

  try {
    const reply = await sendMessage(text);
    addMessage(reply, "bot");
  } catch (error) {
    const fallback =
      "Sorry, I couldn't reach the server. Is the backend running?";
    const message =
      error && error.message
        ? `Server error: ${error.message}`
        : fallback;
    addMessage(message, "bot");
    console.error(error);
  } finally {
    setLoading(false);
  }
});

const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const messagesEl = document.getElementById("messages");
const graphCanvas = document.getElementById("graphCanvas");
const submitButton = chatForm.querySelector("button");
let graphAnimationId = 0;

addMessage("Ask about a ticket, customer history, or a similar resolved case.", false);
showGraphEmptyState();

function addMessage(text, isUser) {
  const div = document.createElement("div");
  div.className = `msg ${isUser ? "msg-user" : "msg-bot"}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

async function addTypingMessage(text) {
  const message = addMessage("", false);
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (prefersReducedMotion) {
    message.textContent = text;
    return;
  }

  for (const character of text) {
    message.textContent += character;
    messagesEl.scrollTop = messagesEl.scrollHeight;
    await new Promise((resolve) => setTimeout(resolve, 14));
  }
}

// Simple radial layout — positions nodes in a circle around the center,
// good enough for a handful of nodes without needing a full graph
// layout library.
function layoutNodes(nodes) {
  const cx = 200, cy = 200, radius = 130;
  return nodes.map((node, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
    return { ...node, x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  });
}

function showGraphEmptyState() {
  const emptyState = document.createElementNS("http://www.w3.org/2000/svg", "text");
  emptyState.setAttribute("x", "200");
  emptyState.setAttribute("y", "200");
  emptyState.setAttribute("class", "graph-empty");
  emptyState.textContent = "Ask about a ticket to trace its relationships";
  graphCanvas.appendChild(emptyState);
}

async function drawGraph(trace) {
  const animationId = ++graphAnimationId;
  graphCanvas.innerHTML = "";
  if (!trace || !trace.nodes || !trace.nodes.length) {
    showGraphEmptyState();
    return;
  }

  const positioned = layoutNodes(trace.nodes);
  const byId = Object.fromEntries(positioned.map((n) => [n.id, n]));

  // Draw edges first (so they sit behind nodes)
  (trace.edges || []).forEach((edge) => {
    const from = byId[edge.from], to = byId[edge.to];
    if (!from || !to) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", from.x);
    line.setAttribute("y1", from.y);
    line.setAttribute("x2", to.x);
    line.setAttribute("y2", to.y);
    line.setAttribute("class", "edge-line");
    graphCanvas.appendChild(line);
  });

  // Draw nodes, revealed one at a time for the "traversal" animation
  for (let i = 0; i < positioned.length; i++) {
    if (animationId !== graphAnimationId) return;
    const node = positioned[i];
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", 0);
    circle.setAttribute("class", "node-circle");
    circle.setAttribute("fill", colorForType(node.type));

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", node.x);
    label.setAttribute("y", node.y + 32);
    label.setAttribute("class", "node-label");
    label.textContent = node.label;

    g.appendChild(circle);
    g.appendChild(label);
    graphCanvas.appendChild(g);

    await new Promise((r) => setTimeout(r, 220));
    if (animationId !== graphAnimationId) return;
    circle.setAttribute("r", 22);
  }
}

function colorForType(type) {
  const colors = {
    Customer: "#B8863F",
    Ticket: "#16233A",
    Product: "#5F7A63",
    IssueType: "#7B93C4",
    History: "#A85445",
    Precedent: "#8F6A2E",
  };
  return colors[type] || "#9099AA";
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  questionInput.value = "";
  addMessage(question, true);
  submitButton.disabled = true;
  questionInput.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
    const data = await res.json();
    await addTypingMessage(data.answer || "I wasn't able to generate a response.");
    drawGraph(data.trace);
  } catch (error) {
    addMessage("The support engine is temporarily unavailable. Please try again.", false);
    console.error(error);
  } finally {
    submitButton.disabled = false;
    questionInput.disabled = false;
    questionInput.focus();
  }
});
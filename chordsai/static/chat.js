// Chat with /chat and play chords in the browser with the Web Audio API.
// Text is inserted with textContent, never as HTML, so a model reply cannot inject markup.
// Sound only starts after a click or key press (browsers block audio before that).
const chat = document.getElementById('chat');
const form = document.getElementById('form');
const input = document.getElementById('input');
const sendButton = document.getElementById('send');
const arpeggio = document.getElementById('arpeggio');
const piano = document.getElementById('piano');

// ------------------------------------------------------------------ sound

let audioContext = null;

function audio() {
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (audioContext.state === 'suspended') void audioContext.resume();
  return audioContext;
}

// One oscillator per note with a short attack and a smooth decay.
function tone(frequency, start, duration, volume) {
  const context = audio();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = 'triangle';
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(start);
  oscillator.stop(start + duration + 0.05);
}

function highlight(midi, delay, duration) {
  const key = piano.querySelector(`[data-midi="${midi}"]`);
  if (!key) return;
  setTimeout(() => key.classList.add('key--active'), delay * 1000);
  setTimeout(() => key.classList.remove('key--active'), (delay + duration) * 1000);
}

// Plays notes together (chord) or one after another (arpeggio). Returns the length in seconds.
function playNotes(notes, offset = 0) {
  const context = audio();
  const spread = arpeggio.checked && notes.length > 1;
  const step = spread ? 0.18 : 0;
  const duration = notes.length > 1 ? 1.6 : 1.1;
  const volume = 0.5 / Math.max(notes.length, 2);
  notes.forEach((note, index) => {
    const delay = offset + index * step;
    tone(note.frequency, context.currentTime + delay, duration, volume);
    highlight(note.midi, delay, Math.min(duration, 0.6));
  });
  return notes.length * step + duration * 0.7;
}

function playSequence(items) {
  let offset = 0;
  for (const item of items) offset += playNotes(item.notes, offset);
}

// ------------------------------------------------------------------- chat

function addMessage(text, kind) {
  const element = document.createElement('div');
  element.className = `message message--${kind}`;
  element.textContent = text;
  chat.append(element);
  element.scrollIntoView({ block: 'end' });
  return element;
}

function addPlayButtons(message, items) {
  if (!Array.isArray(items) || items.length === 0) return;
  const list = document.createElement('div');
  list.className = 'play-list';
  if (items.length > 1) {
    const all = document.createElement('button');
    all.type = 'button';
    all.className = 'play-button play-button--all';
    all.textContent = '▶ Play all';
    all.addEventListener('click', () => playSequence(items));
    list.append(all);
  }
  for (const item of items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'play-button';
    button.textContent = `▶ ${item.name}`;
    button.title = `${item.label}: ${item.notes.map((note) => note.name).join(' ')}`;
    button.addEventListener('click', () => playNotes(item.notes));
    list.append(button);
  }
  message.append(list);
  message.scrollIntoView({ block: 'end' });
}

async function send(message) {
  audio(); // the click that sent the message unlocks sound for the ▶ buttons
  addMessage(message, 'user');
  const pending = addMessage('Thinking…', 'bot');
  pending.classList.add('message--pending');
  sendButton.disabled = true;
  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await response.json().catch(() => ({}));
    pending.textContent = data.reply ?? data.error ?? `Unexpected answer from the server (${response.status}).`;
    if (data.reply) addPlayButtons(pending, data.play);
    else pending.classList.add('message--error');
  } catch {
    pending.textContent = 'Could not reach the server. Check your connection and try again.';
    pending.classList.add('message--error');
  } finally {
    pending.classList.remove('message--pending');
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  void send(message);
});

document.querySelectorAll('[data-example]').forEach((button) => {
  button.addEventListener('click', () => void send(button.dataset.example));
});

// ------------------------------------------------------------------ piano

function keyNote(key) {
  return { midi: Number(key.dataset.midi), frequency: Number(key.dataset.frequency) };
}

piano.addEventListener('pointerdown', (event) => {
  const key = event.target.closest('.key');
  if (!key) return;
  event.preventDefault();
  playNotes([keyNote(key)]);
});

// Keyboard activation (Enter/Space) arrives as a click with detail 0; mouse clicks are handled above.
piano.addEventListener('click', (event) => {
  const key = event.target.closest('.key');
  if (key && event.detail === 0) playNotes([keyNote(key)]);
});

// Computer keyboard: A W S E D F T G Y H U J K = C4 to C5.
const KEY_MAP = 'awsedftgyhujk';
document.addEventListener('keydown', (event) => {
  if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target instanceof HTMLInputElement) return;
  const index = KEY_MAP.indexOf(event.key.toLowerCase());
  if (index < 0) return;
  const key = piano.querySelector(`[data-midi="${60 + index}"]`);
  if (key) playNotes([keyNote(key)]);
});

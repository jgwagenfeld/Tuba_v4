// The script half of Build mode's code <-> 3D link. Pure string work on
// model.py so it is testable without a DOM: the app owns the textarea, this
// owns what a line number and a run length mean.

// A plain positional literal - `builder.run(4.0)`, optionally commented. A
// computed length (`run(L / 2)`) is left to the editor rather than rewritten.
const RUN_CALL = /^(\s*[A-Za-z_][\w.]*\.run\(\s*)(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(\s*\)\s*(?:#.*)?)$/;

export function runLengthLiteral(lineText) {
  const match = RUN_CALL.exec(lineText ?? "");
  return match ? Number(match[2]) : null;
}

export function withRunLength(lineText, length) {
  // Whole numbers keep a float spelling: 5 is written 5.0, like its neighbours.
  const literal = Number.isInteger(length) ? `${length}.0` : String(length);
  return lineText.replace(RUN_CALL, (_match, head, _old, tail) => `${head}${literal}${tail}`);
}

export function lineCount(code) {
  return (code ?? "").split("\n").length;
}

export function scriptLine(code, line) {
  return (code ?? "").split("\n")[line - 1] ?? "";
}

export function replaceScriptLine(code, line, text) {
  const lines = code.split("\n");
  if (!Number.isInteger(line) || line < 1 || line > lines.length) return code;
  lines[line - 1] = text;
  return lines.join("\n");
}

export function lineStartOffset(code, line) {
  const lines = code.split("\n");
  let offset = 0;
  for (let index = 0; index < line - 1 && index < lines.length; index += 1) {
    offset += lines[index].length + 1;
  }
  return offset;
}

export function lineAtOffset(code, offset) {
  return code.slice(0, offset).split("\n").length;
}

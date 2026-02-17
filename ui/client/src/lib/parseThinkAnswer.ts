/**
 * parseThinkAnswer - Extracts thinking and answer content from model responses
 * 
 * Expected formats:
 * 1. Canonical format with explicit tags:
 *    <think>
 *    ...chain-of-thought reasoning...
 *    </think>
 * 
 *    <answer>
 *    ...final response...
 *    </answer>
 * 
 * 2. Legacy format with only <think> tags:
 *    <think>
 *    ...chain-of-thought...
 *    </think>
 *    ...rest of content is the answer...
 * 
 * 3. Plain text (no tags):
 *    ...entire content is the answer...
 * 
 * Returns:
 * - think: The thinking/reasoning content (if present)
 * - answer: The final answer content
 */
export interface ParsedThinkAnswer {
  think: string | null;
  answer: string;
}

/**
 * Parse thinking and answer blocks from raw model response
 */
export function parseThinkAnswer(raw: string): ParsedThinkAnswer {
  if (!raw || typeof raw !== "string") {
    return { think: null, answer: "" };
  }

  // Match <think>...</think> blocks (including multiline, non-greedy)
  const thinkRegex = /<think>([\s\S]*?)<\/think>/;
  const thinkMatch = raw.match(thinkRegex);

  // Match <answer>...</answer> blocks
  const answerRegex = /<answer>([\s\S]*?)<\/answer>/;
  const answerMatch = raw.match(answerRegex);

  // Case 1: Canonical format with explicit answer tag
  if (answerMatch) {
    const answer = answerMatch[1].trim();
    const think = thinkMatch ? thinkMatch[1].trim() : null;
    return { think, answer };
  }

  // Case 2: Legacy format - only <think> tags, rest is answer
  if (thinkMatch) {
    const think = thinkMatch[1].trim();
    // Remove thinking block from content to get answer
    let answer = raw.replace(thinkRegex, "").trim();
    // Clean up extra whitespace (3+ newlines -> 2 newlines)
    answer = answer.replace(/\n{3,}/g, "\n\n");
    return { think, answer };
  }

  // Case 3: No tags found, entire content is the answer
  return { think: null, answer: raw.trim() };
}

/**
 * Check if content contains thinking blocks
 */
export function hasThinkingBlock(raw: string): boolean {
  if (!raw || typeof raw !== "string") return false;
  return /<think>[\s\S]*?<\/think>/.test(raw);
}

/**
 * Strip thinking blocks from content (for plain text display)
 */
export function stripThinkingBlocks(raw: string): string {
  const { answer } = parseThinkAnswer(raw);
  return answer;
}

export default parseThinkAnswer;

/**
 * The two error-shape bugs that made the General Diary screen fail on open.
 *
 * `api.service` normalises every axios failure into `{message, statusCode}`,
 * so `error.response.status` does not survive the interceptor. Both of these
 * were written against the axios shape and neither matched:
 *
 *   1. `getDraft` treated a 404 — "this report has no draft yet", the normal
 *      state of every report — as a real failure, so opening the screen always
 *      alerted before showing anything.
 *   2. The normaliser read `data.message`, but every endpoint in this project
 *      is FastAPI and FastAPI puts the reason in `data.detail`. Every backend
 *      error reached the user as the literal string "An error occurred",
 *      including the ones written to be read.
 */
import { statusOf, messageOf } from './casework.service';

describe('statusOf', () => {
  it('reads the status the interceptor leaves behind', () => {
    expect(statusOf({ message: 'An error occurred', statusCode: 404 })).toBe(404);
  });

  it('still reads a raw axios error, for anything not going through the interceptor', () => {
    expect(statusOf({ response: { status: 404 } })).toBe(404);
  });

  it('is undefined when there is no status at all, such as a dead network', () => {
    expect(statusOf({ message: 'Network error.' })).toBeUndefined();
    expect(statusOf(undefined)).toBeUndefined();
  });
});

describe('messageOf', () => {
  it("prefers the normaliser's message, which now carries FastAPI's detail", () => {
    expect(
      messageOf(
        { message: 'Approve the General Diary before recording a GD number.' },
        'fallback',
      ),
    ).toBe('Approve the General Diary before recording a GD number.');
  });

  it('falls back to a raw axios detail', () => {
    expect(messageOf({ response: { data: { detail: 'No such draft' } } }, 'fallback')).toBe(
      'No such draft',
    );
  });

  it('uses the caller fallback when there is nothing to say', () => {
    expect(messageOf({}, 'Could not load the draft.')).toBe('Could not load the draft.');
  });
});

/**
 * `useDialog` — `Dialog` with the ergonomics of `Alert.alert`.
 *
 * ## The problem this solves
 *
 * `Dialog`'s own note explains why it is not a drop-in for `Alert.alert`:
 * `Alert.alert` is imperative and can be called from anywhere, including a
 * `catch` block, while a React component has to be rendered. That is the right
 * trade — a rendered dialog cannot outlive its screen or stack two deep — but
 * paid once per call site it is three pieces of state and a render for every
 * "Could not save".
 *
 * This holds the state once per screen. The call site goes back to one line:
 *
 * ```tsx
 * const dialog = useDialog();
 * ...
 * catch (error) {
 *   dialog.show({ title: 'Could not save', message: String(error), tone: 'danger' });
 * }
 * ...
 * return (<>
 *   ...
 *   <Dialog {...dialog.props} />
 * </>);
 * ```
 *
 * ## Why it returns props rather than an element
 *
 * A hook that returned JSX would decide where the dialog sits in the tree, and
 * the answer is "last, above everything" — something only the screen knows. It
 * also makes the hook impossible to use from a component that renders a list of
 * them. Props are the smaller promise.
 *
 * ## The one piece of state that is not obvious
 *
 * `visible` is separate from the request, and closing clears only `visible`.
 * `Sheet` animates out, and clearing both at once would blank the title and
 * message for the length of that animation — the dialog visibly emptying
 * itself as it goes. The request is replaced on the next `show`, not on close.
 */

import { useCallback, useMemo, useState } from 'react';

import type { DialogAction, DialogProps, DialogTone } from './Dialog';

export interface DialogRequest {
  title: string;
  message?: string;
  tone?: DialogTone;
  icon?: DialogProps['icon'];
  /**
   * Defaults to a single "OK". Two actions read as a question; three or more
   * are stacked by `Dialog` and read as a chooser.
   */
  actions?: DialogAction[];
  /** Runs after any action, and after a dismissal by scrim or back button. */
  onClose?: () => void;
}

export interface UseDialog {
  /** Raise a dialog. A second call while one is open replaces its contents. */
  show: (request: DialogRequest) => void;
  /** Close whatever is open. Rarely needed — every action closes already. */
  close: () => void;
  /** Spread onto `<Dialog />`. */
  props: DialogProps;
}

export function useDialog(): UseDialog {
  const [request, setRequest] = useState<DialogRequest | null>(null);
  const [visible, setVisible] = useState(false);

  const show = useCallback((next: DialogRequest) => {
    setRequest(next);
    setVisible(true);
  }, []);

  const close = useCallback(() => setVisible(false), []);

  return useMemo<UseDialog>(
    () => ({
      show,
      close,
      props: {
        visible,
        title: request?.title ?? '',
        message: request?.message,
        tone: request?.tone,
        icon: request?.icon,
        actions: request?.actions,
        onClose: () => {
          setVisible(false);
          request?.onClose?.();
        },
      },
    }),
    [visible, request, show, close],
  );
}

export default useDialog;

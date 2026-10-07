/**
 * Supabase Storage helpers.
 *
 * Centralises the avatar upload path so the `<uid>/<filename>` convention lives
 * in one place. That convention is not cosmetic: the storage RLS policies in
 * `backend/migrations/supabase/SCHEMA.sql` authorise writes by checking that the
 * first path segment equals `auth.uid()`. Upload anywhere else and the request
 * is rejected.
 *
 * EditProfileScreen still inlines this logic as of S01; it adopts these helpers
 * when it is decomposed in S08.
 */

import { supabase } from './supabase';

export const AVATARS_BUCKET = 'avatars';

/** Mirrors `allowed_mime_types` on the bucket. Keep the two in sync. */
const ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'heic'] as const;

/** Mirrors `file_size_limit` on the bucket (5 MB). */
const MAX_AVATAR_BYTES = 5 * 1024 * 1024;

function extensionOf(uri: string): string {
  const ext = uri.split('.').pop()?.toLowerCase().split('?')[0] ?? '';
  return ALLOWED_IMAGE_EXTENSIONS.includes(ext as never) ? ext : 'jpg';
}

function mimeTypeFor(extension: string): string {
  if (extension === 'png') return 'image/png';
  if (extension === 'webp') return 'image/webp';
  if (extension === 'heic') return 'image/heic';
  return 'image/jpeg';
}

/**
 * Upload a local image as the signed-in user's avatar and return its public URL.
 *
 * @param userId Must be the signed-in user's id — it becomes the folder name,
 *               and storage RLS requires it to match `auth.uid()`.
 * @param localUri A local file URI, e.g. from expo-image-picker.
 */
export async function uploadAvatar(
  userId: string,
  localUri: string,
): Promise<string> {
  const extension = extensionOf(localUri);
  // Timestamped so the public CDN URL changes on every upload. Without it,
  // `upsert` keeps the same URL and the old image stays cached on device.
  const path = `${userId}/${userId}-${Date.now()}.${extension}`;

  // arrayBuffer() rather than a Blob or FormData: React Native's Blob does not
  // expose the bytes supabase-js needs, and uploads silently produce a 0-byte
  // object.
  const response = await fetch(localUri);
  const bytes = await response.arrayBuffer();

  if (bytes.byteLength === 0) {
    throw new Error('Selected image is empty or could not be read.');
  }
  if (bytes.byteLength > MAX_AVATAR_BYTES) {
    throw new Error(
      `Image is ${(bytes.byteLength / 1024 / 1024).toFixed(1)} MB. ` +
        'Maximum is 5 MB.',
    );
  }

  const { error } = await supabase.storage
    .from(AVATARS_BUCKET)
    .upload(path, bytes, {
      contentType: mimeTypeFor(extension),
      upsert: true,
    });

  if (error) {
    throw new Error(`Avatar upload failed: ${error.message}`);
  }

  const {
    data: { publicUrl },
  } = supabase.storage.from(AVATARS_BUCKET).getPublicUrl(path);

  return publicUrl;
}

/**
 * Delete a previously uploaded avatar, given the public URL stored on the
 * profile. Returns false when the URL does not point at our bucket.
 */
export async function deleteAvatar(publicUrl: string): Promise<boolean> {
  const marker = `/${AVATARS_BUCKET}/`;
  const index = publicUrl.indexOf(marker);
  if (index === -1) return false;

  const path = publicUrl.slice(index + marker.length).split('?')[0];
  const { error } = await supabase.storage.from(AVATARS_BUCKET).remove([path]);

  if (error) {
    throw new Error(`Avatar delete failed: ${error.message}`);
  }
  return true;
}

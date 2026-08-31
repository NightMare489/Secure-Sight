/** Utilities for displaying and validating camera ground-plane homographies. */

export function formatHomography(matrix: number[][] | null | undefined): string {
  return matrix ? JSON.stringify(matrix, null, 2) : '';
}

export function parseHomography(value: string): number[][] | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  let matrix: unknown;
  try {
    matrix = JSON.parse(trimmed);
  } catch {
    throw new Error('Homography must be valid JSON.');
  }

  if (
    !Array.isArray(matrix)
    || matrix.length !== 3
    || matrix.some(
      (row) => !Array.isArray(row)
        || row.length !== 3
        || row.some((value) => typeof value !== 'number' || !Number.isFinite(value)),
    )
  ) {
    throw new Error('Homography must be a 3×3 matrix of finite numbers.');
  }

  const determinant =
    matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
    - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
    + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]);
  if (Math.abs(determinant) < 1e-12) {
    throw new Error('Homography must be non-singular.');
  }

  return matrix as number[][];
}

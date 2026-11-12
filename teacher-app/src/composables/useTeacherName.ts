/**
 * Shared composable: teacher name display in top bar.
 * Reads from localStorage (set by LoginView on login).
 */
import { ref } from "vue";

export function useTeacherName() {
  const teacherName = ref(localStorage.getItem("horn_teacher_name") || "");
  return { teacherName };
}

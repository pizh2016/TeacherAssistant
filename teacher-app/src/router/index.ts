import { createRouter, createWebHashHistory } from "vue-router";
import { isAuthenticated } from "@/api";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: "/login",
      name: "Login",
      component: () => import("@/views/LoginView.vue"),
      meta: { guest: true },
    },
    {
      path: "/",
      name: "Home",
      component: () => import("@/views/HomeView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/history",
      name: "History",
      component: () => import("@/views/HistoryView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/classes",
      name: "Classes",
      component: () => import("@/views/ClassManageView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/templates",
      name: "Templates",
      component: () => import("@/views/TemplatesView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/schedule",
      name: "Schedule",
      component: () => import("@/views/ScheduleView.vue"),
      meta: { requiresAuth: true },
    },
  ],
});

// 导航守卫：未登录跳转登录页
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    return { name: "Login" };
  }
  if (to.meta.guest && isAuthenticated()) {
    return { name: "Home" };
  }
});

export default router;

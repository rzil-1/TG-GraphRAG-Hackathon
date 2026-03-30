import { useState, useEffect, useCallback } from "react";

export interface RolesState {
  userRoles: string[];
  graphRoles: Record<string, string[]>;
  rolesLoaded: boolean;
  hasCreds: boolean;
  selectedGraph: string;
  isSuperuser: boolean;
  isGlobalDesigner: boolean;
  isGraphAdmin: boolean;
  canAccessSetup: boolean;
}

function parseGraphRoles(raw: unknown): Record<string, string[]> {
  if (!raw || typeof raw !== "object") return {};
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).map(([graph, roles]) => [
      graph,
      Array.isArray(roles)
        ? roles.map((role: string) => role.toLowerCase())
        : [],
    ])
  );
}

export function useRoles(refreshKey?: unknown): RolesState {
  const [userRoles, setUserRoles] = useState<string[]>([]);
  const [graphRoles, setGraphRoles] = useState<Record<string, string[]>>({});
  const [rolesLoaded, setRolesLoaded] = useState(false);
  const [hasCreds, setHasCreds] = useState(false);
  const [selectedGraph, setSelectedGraph] = useState(
    localStorage.getItem("selectedGraph") || ""
  );

  const fetchRoles = useCallback(async () => {
    const creds = localStorage.getItem("creds");
    if (!creds) {
      setUserRoles([]);
      setGraphRoles({});
      setHasCreds(false);
      setRolesLoaded(true);
      return;
    }
    try {
      const response = await fetch("/ui/roles", {
        headers: { Authorization: `Basic ${creds}` },
      });
      if (!response.ok) {
        setUserRoles([]);
        setGraphRoles({});
        setHasCreds(false);
        setRolesLoaded(true);
        return;
      }
      const data = await response.json();
      const roles = Array.isArray(data.roles) ? data.roles : [];
      setUserRoles(roles.map((role: string) => role.toLowerCase()));
      setGraphRoles(parseGraphRoles(data.graph_roles));
      setSelectedGraph(localStorage.getItem("selectedGraph") || "");
      setHasCreds(true);
    } finally {
      setRolesLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchRoles();
  }, [fetchRoles, refreshKey]);

  useEffect(() => {
    const handleGraphChange = () => {
      setSelectedGraph(localStorage.getItem("selectedGraph") || "");
    };
    window.addEventListener("graphrag:selectedGraph", handleGraphChange);
    return () => {
      window.removeEventListener("graphrag:selectedGraph", handleGraphChange);
    };
  }, []);

  const selectedGraphRoles = graphRoles[selectedGraph] || [];
  const isSuperuser = userRoles.includes("superuser");
  const isGlobalDesigner = userRoles.includes("globaldesigner");
  const isGraphAdmin = selectedGraphRoles.includes("admin");
  const canAccessSetup = isSuperuser || isGlobalDesigner || isGraphAdmin;

  return {
    userRoles,
    graphRoles,
    rolesLoaded,
    hasCreds,
    selectedGraph,
    isSuperuser,
    isGlobalDesigner,
    isGraphAdmin,
    canAccessSetup,
  };
}

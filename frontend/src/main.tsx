import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Workspace } from "./workspace/Workspace";
import { PlatformProvider } from "./platform/PlatformContext";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/instrument.css";

const container = document.getElementById("root");
if (!container) throw new Error("Missing #root");

// PlatformProvider resolves where the backend is and configures the API
// client before rendering anything, so no component below it has to know
// whether it is running in a browser or inside the desktop shell.
createRoot(container).render(
  <StrictMode>
    <PlatformProvider>
      <Workspace />
    </PlatformProvider>
  </StrictMode>,
);

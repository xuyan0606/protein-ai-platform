declare var $3Dmol: {
  createViewer: (element: HTMLElement | string, config?: Record<string, unknown>) => $3Dmol.GLViewer
  SurfaceType: { VDW: number; SAS: number; SES: number }
}

declare namespace $3Dmol {
  class GLViewer {
    addModel(data: string, format: string): GLModel
    removeAllModels(): void
    setStyle(sel: Record<string, unknown>, style: Record<string, unknown>): void
    addSurface(type: number, style: Record<string, unknown>): void
    zoomTo(): void
    zoom(factor: number): void
    render(callback?: () => void): void
    resize(width?: number, height?: number): void
    setBackgroundColor(color: string | number, alpha?: number): void
    spin(axis?: string | boolean): void
    clear(): void
    getModel(): GLModel
  }

  class GLModel {
    setStyle(sel: Record<string, unknown>, style: Record<string, unknown>): void
    setAtomStyle(sel: Record<string, unknown>, style: Record<string, unknown>): void
    setColorByResidue(): void
  }
}

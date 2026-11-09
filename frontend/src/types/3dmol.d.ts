declare module '3dmol/build/3Dmol.js'

declare namespace $3Dmol {
  class GLViewer {
    removeAllModels(): void
    addModel(data: string, format: string): void
    setStyle(sel: object, style: object): void
    addSurface(type: SurfaceType, style: object): void
    zoomTo(): void
    render(): void
    clear(): void
    setBackgroundColor(color: string): void
    resize(): void
  }

  enum SurfaceType {
    VDW = 0,
    MS = 1,
    SAS = 2,
  }

  function createViewer(element: HTMLElement, options?: object): GLViewer
}

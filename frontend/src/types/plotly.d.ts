/**
 * Minimal type declaration for plotly.js-dist-min.
 * The package ships JavaScript only; we use `any` for the Plotly
 * instance since trace/layout/config objects are constructed as
 * plain objects in our components.
 */
declare module 'plotly.js-dist-min' {
  const Plotly: any
  export default Plotly
}

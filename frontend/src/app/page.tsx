export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">RustDALI Server</h1>
      <p className="text-gray-600">
        Protein structural search against ECOD domain and PDB chain libraries.
      </p>
      <div className="flex gap-4 mt-6">
        <a
          href="/submit"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Submit a search
        </a>
        <a
          href="/jobs"
          className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
        >
          View jobs
        </a>
      </div>
    </div>
  );
}

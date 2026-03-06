import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">RustDALI Server</h1>
        <p className="text-gray-600 mt-1">
          Protein structural search against ECOD domain and PDB chain
          libraries, powered by dali_rust.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 max-w-2xl">
        <Link
          href="/submit"
          className="block bg-white border border-gray-200 rounded-lg p-5 hover:border-blue-300 transition-colors"
        >
          <h2 className="font-semibold text-blue-600 mb-1">Submit a search</h2>
          <p className="text-sm text-gray-500">
            Upload a PDB/CIF structure and search against ECOD or PDB
            libraries.
          </p>
        </Link>
        <Link
          href="/jobs"
          className="block bg-white border border-gray-200 rounded-lg p-5 hover:border-blue-300 transition-colors"
        >
          <h2 className="font-semibold text-blue-600 mb-1">View jobs</h2>
          <p className="text-sm text-gray-500">
            Check the status of your searches and browse results.
          </p>
        </Link>
      </div>
    </div>
  );
}

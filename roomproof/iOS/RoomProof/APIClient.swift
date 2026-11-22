import Foundation
import Security
import RoomProofCore

struct HealthResponse: Decodable { var contractVersion: Int; var geminiConfigured: Bool; var tinyfishConfigured: Bool }
struct AnalysisResponse: Decodable {
    var contractVersion: Int; var requestId: String; var revision: Int
    var preferClosedStorage: Bool; var style: String; var questions: [String]; var summary: String; var provider: String; var model: String
}
struct JobStart: Decodable { var jobId: String; var requestId: String; var revision: Int }
struct SourceJob: Decodable {
    var contractVersion: Int; var jobId: String; var requestId: String; var revision: Int
    var state: String; var progress: [String]; var offers: [OfferSnapshot]; var errors: [String]
}
private struct APIProblem: Decodable { var code: String; var message: String; var retryable: Bool }
struct ClientError: LocalizedError { let message: String; var code: String? = nil; var errorDescription: String? { message } }

private final class NoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}

struct APIClient {
    let baseURL: String
    let token: String
    static func isPrivateHost(_ host: String) -> Bool {
        let host = host.lowercased()
        if host == "localhost" || host == "::1" || host == "[::1]" || host.hasSuffix(".local") { return true }
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        let octets = parts.compactMap { Int($0) }
        guard parts.count == 4, octets.count == 4, octets.allSatisfy({ (0...255).contains($0) }) else { return false }
        return octets[0] == 10 || octets[0] == 127 || (octets[0] == 192 && octets[1] == 168) || (octets[0] == 172 && (16...31).contains(octets[1]))
    }
    private func request<T: Decodable>(_ path: String, body: Data? = nil) async throws -> T {
        guard let base = URL(string: baseURL), ["http", "https"].contains(base.scheme ?? ""),
              let host = base.host, !host.isEmpty, base.user == nil, base.password == nil,
              !token.isEmpty else { throw ClientError(message: "Connect your Mac in Settings before using Gemini or retailer checks.") }
        guard base.scheme == "https" || Self.isPrivateHost(host) else { throw ClientError(message: "Use a private Mac address for HTTP, or an HTTPS address.") }
        let url = base.appendingPathComponent("api/roomproof").appendingPathComponent(path)
        var request = URLRequest(url: url); request.httpMethod = body == nil ? "GET" : "POST"
        request.timeoutInterval = 35; request.httpBody = body
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let session = URLSession(configuration: .ephemeral, delegate: NoRedirects(), delegateQueue: nil)
        defer { session.finishTasksAndInvalidate() }
        let (data, response) = try await session.data(for: request)
        guard data.count < 2_000_000, let http = response as? HTTPURLResponse else { throw ClientError(message: "The Mac returned an invalid response.") }
        guard (200..<300).contains(http.statusCode) else {
            if let problem = try? JSONDecoder().decode(APIProblem.self, from: data) { throw ClientError(message: problem.message, code: problem.code) }
            throw ClientError(message: "Mac service returned HTTP \(http.statusCode). Check the connection and try again.")
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw ClientError(message: "The app and Mac returned different data formats. Update both to contract version 1.") }
    }
    func health() async throws -> HealthResponse {
        let health: HealthResponse = try await request("health")
        guard health.contractVersion == 1 else { throw ClientError(message: "Update the app and Mac service to the same contract version.") }
        return health
    }
    func analyze(project: ProjectDocument, image: Data?) async throws -> AnalysisResponse {
        struct Payload: Encodable {
            var requestId: String; var revision: Int; var text: String; var room: RoomSpec; var brief: DesignBrief; var imageBase64: String?
        }
        if let image, image.count > 10 * 1024 * 1024 { throw ClientError(message: "Choose a photo smaller than 10 MB.") }
        let body = Payload(requestId: UUID().uuidString, revision: project.revision, text: project.brief.notes, room: project.room, brief: project.brief, imageBase64: image?.base64EncodedString())
        let response: AnalysisResponse = try await request("analyze", body: JSONEncoder().encode(body))
        guard response.requestId == body.requestId, response.revision == body.revision, response.contractVersion == 1 else { throw ClientError(message: "The Gemini response did not match this brief. Try again.") }
        return response
    }
    func startSourcing(revision: Int, requestId: String) async throws -> JobStart {
        struct Payload: Encodable { var requestId: String; var revision: Int; var storeLocation: String }
        let payload = Payload(requestId: requestId, revision: revision, storeLocation: "London, Ontario, Canada")
        let response: JobStart = try await request("sourcing", body: JSONEncoder().encode(payload))
        guard response.requestId == payload.requestId, response.revision == revision else { throw ClientError(message: "The retailer job did not match this request.") }
        return response
    }
    func job(_ id: String) async throws -> SourceJob { try await request("jobs/" + id) }
}

enum PairingKeychain {
    private static let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "dev.tejask.RoomProof", kSecAttrAccount as String: "mac-pairing"]
    static func read() -> String {
        var q = query; q[kSecReturnData as String] = true
        var item: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }
    static func write(_ token: String) -> Bool {
        let attrs: [String: Any] = [kSecValueData as String: Data(token.utf8), kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        let result = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if result == errSecSuccess { return true }
        guard result == errSecItemNotFound else { return false }
        return SecItemAdd(query.merging(attrs) { _, new in new } as CFDictionary, nil) == errSecSuccess
    }
}

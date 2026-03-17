import SwiftUI
import Charts

struct QuadrantPanelView: View {
    @EnvironmentObject private var bridge: PythonBridgeService
    @State private var isLoading = false
    @State private var showList = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Eisenhower Matrix")
                .font(.custom("Avenir Next Demi Bold", size: 28))
                
            HStack {
                Button("分析7天日程") {
                    fetchData(period: "7days")
                }.disabled(isLoading)
                
                Button("分析近期日程(今日至明早)") {
                    fetchData(period: "today")
                }.disabled(isLoading)
                
                Toggle("显示详细列表", isOn: $showList)
                    .toggleStyle(.switch)
                    .padding(.leading, 10)
                
                if isLoading {
                    ProgressView().controlSize(.small)
                        .padding(.leading, 10)
                }
            }
            
            if bridge.quadrantItems.isEmpty {
                Text("暂无数据，请点击上方按钮进行AI分析。")
                    .foregroundStyle(.secondary)
                Spacer()
            } else {
                HStack(spacing: 20) {
                    // Scatter Plot
                    Chart(bridge.quadrantItems) { item in
                        PointMark(
                            x: .value("Urgency", Double(item.urgency) + jitterX(for: item.title)),
                            y: .value("Importance", Double(item.importance) + jitterY(for: item.title))
                        )
                        .foregroundStyle(color(for: item.quadrant))
                        .symbolSize(200)
                        .annotation(position: .top, spacing: 4) {
                            Text(item.title)
                                .font(.system(size: 10, weight: .semibold))
                                .padding(.horizontal, 6)
                                .padding(.vertical, 3)
                                .background(Color(.windowBackgroundColor).opacity(0.85))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                                .overlay(RoundedRectangle(cornerRadius: 6).stroke(color(for: item.quadrant).opacity(0.5), lineWidth: 1))
                                .shadow(color: .black.opacity(0.1), radius: 2, x: 0, y: 1)
                                .frame(maxWidth: 90)
                                .lineLimit(1)
                        }
                    }
                    .chartXScale(domain: [0, 11])
                    .chartYScale(domain: [0, 11])
                    .chartXAxis {
                        AxisMarks(values: .stride(by: 1))
                    }
                    .chartYAxis {
                        AxisMarks(values: .stride(by: 1))
                    }
                    // Dividers for matrix
                    .chartOverlay { proxy in
                        GeometryReader { geo in
                            if let midX = proxy.position(forX: 5.5),
                               let midY = proxy.position(forY: 5.5) {
                                Path { path in
                                    // Vertical line
                                    path.move(to: CGPoint(x: midX, y: 0))
                                    path.addLine(to: CGPoint(x: midX, y: geo.size.height))
                                    // Horizontal line
                                    path.move(to: CGPoint(x: 0, y: midY))
                                    path.addLine(to: CGPoint(x: geo.size.width, y: midY))
                                }
                                .stroke(Color.gray.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [5, 5]))
                                
                                // Labels
                                Text("Q2: Schedule").font(.body.bold()).opacity(0.3).position(x: mapX(xy: 8.25, proxy: proxy), y: mapY(xy: 8.25, proxy: proxy))
                                Text("Q1: Do First").font(.body.bold()).opacity(0.3).position(x: mapX(xy: 2.75, proxy: proxy), y: mapY(xy: 8.25, proxy: proxy))
                                Text("Q3: Delegate").font(.body.bold()).opacity(0.3).position(x: mapX(xy: 2.75, proxy: proxy), y: mapY(xy: 2.75, proxy: proxy))
                                Text("Q4: Delete").font(.body.bold()).opacity(0.3).position(x: mapX(xy: 8.25, proxy: proxy), y: mapY(xy: 2.75, proxy: proxy))
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    
                    if showList {
                        List(bridge.quadrantItems) { item in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(item.title).font(.headline)
                                    Spacer()
                                    Text(item.quadrant)
                                        .font(.caption.bold())
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(color(for: item.quadrant).opacity(0.2))
                                        .foregroundColor(color(for: item.quadrant))
                                        .clipShape(Capsule())
                                }
                                Text(item.description)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                        .scrollIndicators(.visible)
                        .frame(width: 300)
                    }
                }
            }
        }
    }
    
    private func mapX(xy: Double, proxy: ChartProxy) -> CGFloat {
        proxy.position(forX: xy) ?? 0
    }
    private func mapY(xy: Double, proxy: ChartProxy) -> CGFloat {
        proxy.position(forY: xy) ?? 0
    }
    
    private func fetchData(period: String) {
        Task {
            isLoading = true
            await bridge.loadQuadrantAnalysis(period: period)
            isLoading = false
        }
    }
    
    private func color(for quadrant: String) -> Color {
        if quadrant.hasPrefix("Q1") { return .red }
        if quadrant.hasPrefix("Q2") { return .blue }
        if quadrant.hasPrefix("Q3") { return .orange }
        if quadrant.hasPrefix("Q4") { return .gray }
        return .primary
    }
    
    // Simple deterministic jitter based on title to separate overlapping points
    private func jitterX(for string: String) -> Double {
        let hash = string.hashValue
        let normalized = Double(abs(hash) % 100) / 100.0 // 0 to 1
        return (normalized * 0.4) - 0.2 // Jitter between -0.2 and +0.2
    }
    
    private func jitterY(for string: String) -> Double {
        let hash = String(string.reversed()).hashValue
        let normalized = Double(abs(hash) % 100) / 100.0 // 0 to 1
        return (normalized * 0.4) - 0.2 // Jitter between -0.2 and +0.2
    }
}

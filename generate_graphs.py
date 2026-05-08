import matplotlib.pyplot as plt
import numpy as np

# 1. Accuracy Comparison
modules = ['Domain Classification', 'Legal Retrieval', 'Emotion Detection']
accuracy = [94.2, 89.1, 91.3]

plt.figure()
plt.bar(modules, accuracy)
plt.xlabel('Modules')
plt.ylabel('Accuracy (%)')
plt.title('Accuracy Comparison Across Modules')
plt.xticks(rotation=20)
plt.tight_layout()
plt.savefig('accuracy_comparison.png')
plt.close()

# 2. Precision vs Recall
models = ['Classifier', 'Emotion Model']
precision = [94.8, 92.5]
recall = [93.6, 90.1]

plt.figure()
plt.plot(models, precision, marker='o', label='Precision')
plt.plot(models, recall, marker='o', label='Recall')
plt.xlabel('Models')
plt.ylabel('Score (%)')
plt.title('Precision vs Recall')
plt.legend()
plt.grid()
plt.savefig('precision_recall.png')
plt.close()

# 3. Confusion Matrix
cm = np.array([[378, 22],
               [18, 382]])

plt.figure()
plt.imshow(cm)
plt.title('Confusion Matrix')
plt.xlabel('Predicted')
plt.ylabel('Actual')

for i in range(len(cm)):
    for j in range(len(cm)):
        plt.text(j, i, cm[i][j], ha='center', va='center')

plt.colorbar()
plt.savefig('confusion_matrix.png')
plt.close()

# 4. Response Quality Histogram
ratings = [5]*320 + [4]*290 + [3]*140 + [2]*40 + [1]*10

plt.figure()
plt.hist(ratings, bins=5)
plt.xlabel('Rating')
plt.ylabel('Frequency')
plt.title('Response Quality Distribution')
plt.savefig('response_quality.png')
plt.close()

# 5. Latency vs Complexity
complexity = [1,2,3,4,5]
latency = [1.2,1.5,2.2,2.9,3.6]

plt.figure()
plt.plot(complexity, latency, marker='o')
plt.xlabel('Query Complexity')
plt.ylabel('Response Time (s)')
plt.title('Latency vs Query Complexity')
plt.grid()
plt.savefig('latency.png')
plt.close()

print("All figures saved successfully!")
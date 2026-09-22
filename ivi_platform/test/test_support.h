#pragma once

#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

inline void expectTrue(bool condition, const char* expression, const char* file, int line) {
    if (!condition) {
        throw std::runtime_error(std::string(file) + ":" + std::to_string(line) +
                                 " expectation failed: " + expression);
    }
}

inline void expectNear(double actual,
                       double expected,
                       double tolerance,
                       const char* expression,
                       const char* file,
                       int line) {
    if (std::fabs(actual - expected) > tolerance) {
        throw std::runtime_error(std::string(file) + ":" + std::to_string(line) +
                                 " expectation failed: " + expression + " actual=" +
                                 std::to_string(actual) + " expected=" + std::to_string(expected));
    }
}

#define EXPECT_TRUE(value) expectTrue((value), #value, __FILE__, __LINE__)
#define EXPECT_FALSE(value) expectTrue(!(value), "!(" #value ")", __FILE__, __LINE__)
#define EXPECT_EQ(actual, expected) expectTrue((actual) == (expected), #actual " == " #expected, __FILE__, __LINE__)
#define EXPECT_NEAR(actual, expected, tolerance) \
    expectNear((actual), (expected), (tolerance), #actual " ~= " #expected, __FILE__, __LINE__)

template <typename Function>
int runTestProgram(const char* name, Function function) {
    try {
        function();
        std::cout << "PASS: " << name << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << name << ": " << error.what() << '\n';
        return 1;
    }
}
